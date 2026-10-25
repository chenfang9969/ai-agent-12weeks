# -*- coding: utf-8 -*-
r"""LLM Rerank 练习（W03 Day 6）

要你填的只有两个函数：judge() 和 rerank()。

跑法:
    python rerank_test.py                    # 跑三个失败案例，对比 rerank 前后
    python rerank_test.py --question "xxx"   # 只测一个问题

为什么这么做：
    现在的检索按"字面重叠"排序，问"保修期"找不到"服务期"。
    让 LLM 来判断"这段能不能回答这个问题"，它天生懂同义词。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ai-research-agent"))

import rag  # noqa: E402
from llm import chat, pick_provider  # noqa: E402


# ==========================================================================
# TODO 1：判断一段资料能不能回答某个问题
# ==========================================================================
def judge(question: str, chunk_text: str) -> int:
    """让 LLM 给 0-10 分。

    要求：
      1. 构造一个 prompt，让模型只回一个数字
      2. 提示词要写清楚评分标准，例如：
           10 = 这段直接包含答案
            7 = 这段包含答案的一部分
            3 = 这段和问题有点关系但答不了
            0 = 完全无关
      3. 解析返回的文本，取出数字
      4. 解析失败就返回 0（宁可当无关，不要崩）
      5. temperature 设 0，让它稳定

    返回 0-10 的整数。
    """
    # TODO: 请在这里实现
    resp = chat(pick_provider(), [
        {"role": "system", "content": "你是资料相关性评审。只输出一个 0-10 的整数，不要任何解释。"},
        {"role": "user", "content": f"""问题：{question}

            资料：
            {chunk_text[:800]}

            请判断这段资料能不能回答问题，按下面标准打分：
            10 = 直接包含答案
            7 = 包含答案的一部分
            3 = 和问题有关但答不了
            0 = 完全无关

            只输出数字："""},
                ], temperature=0)  
    import re
    text = resp.text.strip()
    m = re.search(r"\d+", text)      # 从回复里抠出数字（可能回"8分"或"评分：8"）
    if not m:
        return 0                      # 抠不到就当无关，不要崩
    score = int(m.group())
    return max(0, min(10, score)) 


# ==========================================================================
# TODO 2：按 LLM 的分数重排
# ==========================================================================
def rerank(question: str, hits: list[dict], keep: int = 3, min_score: int = 5) -> list[dict]:
    """对每个候选片段打分、排序、过滤。

    要求：
      1. 对 hits 里每一段调用 judge(question, h["text"])
      2. 把分数存进 h["llm_score"]
      3. 按 llm_score 从高到低排序
      4. 丢掉 llm_score < min_score 的
      5. 最多保留 keep 个

    返回新的列表（不要改原列表顺序）。
    """
    # TODO: 请在这里实现
    scored = []                              # ① 新建一个列表，不动原数据
    for h in hits:
        s = judge(question, h["text"])
        scored.append({**h, "llm_score": s}) # ② 复制一份 + 附上分数

    scored.sort(key=lambda x: x["llm_score"], reverse=True)   # ③ 全部打完分才排序

    kept = [h for h in scored if h["llm_score"] >= min_score] # ④ 过滤掉低分
    return kept[:keep]   

# ==========================================================================
# 以下是测试，不用改
# ==========================================================================
CASES = [
    ("产品保修期多久？", "服务期"),
    ("标准版含有什么服务？", "标准"),
    ("有故障怎么办？", "故障"),
]


def run_case(question: str, expect_kw: str) -> bool:
    idx = rag.load_index()
    # 故意用很低的门槛，先多捞一些候选出来，交给 rerank 筛
    hits = rag.search(idx, question, top_k=8, min_score=0.01, rel_threshold=0.0)

    print("=" * 70)
    print(f"问题: {question}    期望命中关键词: {expect_kw!r}")
    print("=" * 70)

    print("\n【rerank 之前】字面检索的结果：")
    if not hits:
        print("  (什么都没捞到)")
    for h in hits:
        mark = "✅含答案" if expect_kw in h["text"] else "  "
        print(f"  {h['score']:.3f}  {mark} {h['source']} - {h['title']}")

    before_ok = any(expect_kw in h["text"] for h in hits[:3])

    # rerank
    try:
        reranked = rerank(question, hits, keep=3, min_score=3)
    except NotImplementedError as e:
        print(f"\n[还没做完] {e}")
        return False

    print("\n【rerank 之后】按 LLM 分数重排：")
    if not reranked:
        print("  (全部被过滤掉 —— 等于拒答)")
    for h in reranked:
        mark = "✅含答案" if expect_kw in h["text"] else "  "
        print(f"  LLM={h.get('llm_score', '?')}  {mark} {h['source']} - {h['title']}")

    after_ok = any(expect_kw in h["text"] for h in reranked[:3])
    print()
    print(f"  排序前 Top3 里有答案: {'是' if before_ok else '否'}")
    print(f"  排序后 Top3 里有答案: {'是' if after_ok else '否'}")
    if after_ok and not before_ok:
        print("  >>> 救回来了 <<<")
    return after_ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", help="只测这一个问题")
    ap.add_argument("--expect", default="", help="配合 --question，期望出现的关键词")
    a = ap.parse_args()

    cases = [(a.question, a.expect)] if a.question else CASES
    passed = 0
    for q, kw in cases:
        if run_case(q, kw):
            passed += 1
        print()

    print("=" * 70)
    print(f"  通过 {passed}/{len(cases)}")
    print("=" * 70)
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
