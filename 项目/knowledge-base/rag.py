# -*- coding: utf-8 -*-
"""企业知识库 Agent —— RAG 最小可用版（W03 Day1-Day4 的骨架）

设计原则：**先用最土的办法跑通，再考虑换向量库。**
  - 切片：按 markdown 标题层级切 + 重叠窗口
  - 检索：TF-IDF 风格的词频打分（零依赖，够用）
  - 生成：把 Top-K 片段塞进 Prompt，要求带引用

为什么不用 Chroma/Milvus 起步？
  因为你现在缺的是"检索效果好不好"的判断力，不是"向量库会不会用"。
  先用词频跑，你会亲眼看到"切片方式"对结果的影响 —— 这是 RAG 的核心功夫。

用法:
    python rag.py --build                 # 建索引
    python rag.py --ask "如何处理客户投诉"
    python rag.py --eval                  # 跑评测集
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ai-research-agent"))

DATA = HERE / "data"
INDEX = HERE / "index.json"


# --------------------------------------------------------------------------
# 1. 切片：RAG 质量的 70% 在这一步
# --------------------------------------------------------------------------
def split_markdown(text: str, source: str, max_chars: int = 400, overlap: int = 80,
                   min_block_chars: int = 120) -> list[dict]:
    """按标题层级切，再按长度切，带重叠。

    两个关键参数，也是 W03 要做的对照实验：
      overlap   重叠窗口 —— 防止一句话被切断后检索不到；代价是索引变大、召回重复
      min_block 最小块 —— 太碎的块（比如只有一行"## 价格方案"）检索时是纯噪声

    真实调优经验：先调 min_block 合并碎片，再调 overlap，最后才考虑换向量模型。
    """
    chunks: list[dict] = []
    # 先按二级/三级标题分段
    sections = re.split(r"(?m)^(#{1,3})\s+(.+)$", text)
    blocks: list[tuple[str, str]] = []
    if len(sections) >= 4:
        for i in range(1, len(sections), 3):
            title = sections[i + 1].strip()
            body = sections[i + 2] if i + 2 < len(sections) else ""
            blocks.append((title, body.strip()))
    else:
        blocks.append((source, text.strip()))

    # ★ 合并过小的相邻块：碎片化是检索噪声的头号来源
    merged: list[tuple[str, str]] = []
    for title, body in blocks:
        if merged and len(merged[-1][1]) < min_block_chars:
            prev_title, prev_body = merged[-1]
            merged[-1] = (prev_title, f"{prev_body}\n\n## {title}\n{body}".strip())
        else:
            merged.append((title, body))
    # 收尾：如果最后一块太小，并进前一块
    if len(merged) > 1 and len(merged[-1][1]) < min_block_chars:
        t, b = merged.pop()
        pt, pb = merged[-1]
        merged[-1] = (pt, f"{pb}\n\n## {t}\n{b}".strip())

    for title, body in merged:
        body = body.strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append({
                "id": f"{source}#{len(chunks)}",
                "source": source,
                "title": title,
                "text": body,
            })
            continue
        start = 0
        while start < len(body):
            piece = body[start:start + max_chars]
            if piece.strip():
                chunks.append({
                    "id": f"{source}#{len(chunks)}",
                    "source": source,
                    "title": title,
                    "text": piece.strip(),
                })
            if start + max_chars >= len(body):
                break
            start += max_chars - overlap
    return chunks


# --------------------------------------------------------------------------
# 2. 检索：词频打分（中文用 2-gram，够土够用）
# --------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    t = re.sub(r"\s+", "", text.lower())
    grams = [t[i:i + 2] for i in range(len(t) - 1)]          # 中文 2-gram
    grams += re.findall(r"[a-z0-9]{2,}", text.lower())        # 英文/数字词
    return grams


def build_index(chunks: list[dict]) -> dict:
    df: Counter = Counter()
    for c in chunks:
        for g in set(tokenize(c["text"] + c["title"])):
            df[g] += 1
    n = max(len(chunks), 1)
    idf = {g: math.log((n + 1) / (v + 1)) + 1 for g, v in df.items()}
    for c in chunks:
        c["tokens"] = tokenize(c["text"] + c["title"])
    return {"chunks": chunks, "idf": idf, "n": n}


def search(index: dict, query: str, top_k: int = 3,
           min_score: float = 0.25, rel_threshold: float = 0.45) -> list[dict]:
    """词频打分检索。两道闸门，缺一不可：

    min_score    绝对下限：分数低于此值视为"不相关"。实测无关问题最高只有 0.147，
                 而真正相关的问题在 1.0 以上 —— 所以 0.25 是个安全的门槛。
    rel_threshold 相对阈值：低于"最高分 × 该比例"的也丢弃。

    为什么必须有绝对下限：
        Top-K 一定会凑满 K 个结果，哪怕全都无关。把噪声当资料喂给 LLM，
        是 RAG 答错的头号原因。**宁少勿滥，宁可拒答也不许瞎答。**
        这两句话，就是你以后卖给企业客户的核心承诺。
    """
    idf = index["idf"]
    q_tokens = tokenize(query)
    scored = []
    for c in index["chunks"]:
        tf = Counter(c["tokens"])
        score = sum(tf.get(g, 0) * idf.get(g, 1.0) for g in q_tokens)
        # 长度归一化：防止长片段靠"字多"取胜
        score /= math.sqrt(len(c["tokens"]) + 1)
        if score > 0:
            scored.append((score, c))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[0])
    cut = max(min_score, scored[0][0] * rel_threshold)
    kept = [(s, c) for s, c in scored[:top_k] if s >= cut]
    return [{**c, "score": round(s, 3)} for s, c in kept]


# --------------------------------------------------------------------------
# 3. 生成：资料塞进 Prompt，强制带引用
# --------------------------------------------------------------------------
SYSTEM = """你是企业知识库助手。只能依据【参考资料】回答，规则：
1. 资料里有答案 → 回答，并在句末标注来源，格式 [来源: 文件名 - 小标题]
2. 资料里没有 → 明确回答"资料中没有找到相关内容，建议咨询____"，绝对不许编造
3. 回答先给结论，再给依据要点，控制在 200 字内
4. 涉及金额、合同、法律条款时，结尾提醒"建议人工复核"
"""


def answer(question: str, hits: list[dict], use_llm: bool = True) -> str:
    if not hits:
        return "资料中没有找到相关内容，建议咨询相关同事。"
    ctx = "\n\n".join(
        f"【资料{i + 1}】来源: {h['source']} - {h['title']}\n{h['text']}" for i, h in enumerate(hits)
    )
    if not use_llm:
        return f"(检索结果，未调用 LLM)\n\n{ctx}"

    from llm import chat, pick_provider
    p = pick_provider()
    r = chat(p, [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"【参考资料】\n{ctx}\n\n【问题】{question}"},
    ], temperature=0.2)
    return r.text


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_build(max_chars: int = 400, overlap: int = 80, min_block: int = 120):
    """建索引。三个参数就是 W03 要做的对照实验：
        max_chars  每片最长多少字
        overlap    相邻片重叠多少字（防止一句话被切断）
        min_block  小于这个字数的碎片会被合并进上一片（防止标题独占一片）

    跑法：
        python rag.py --build                          # 默认 400/80/120
        python rag.py --build --max-chars 200          # 实验 A
        python rag.py --build --overlap 0              # 实验 B
    """
    if not DATA.exists():
        print(f"[!] 没有资料目录: {DATA}")
        print("    W03 Day1 任务：在 data/ 下建 4 类资料（产品资料/员工手册/培训文档/销售资料）")
        return 1
    files = [p for p in DATA.rglob("*") if p.suffix.lower() in (".md", ".txt")]
    if not files:
        print(f"[!] {DATA} 下没有 .md/.txt 资料")
        return 1
    chunks: list[dict] = []
    for f in files:
        chunks += split_markdown(f.read_text(encoding="utf-8", errors="ignore"), f.name,
                                 max_chars=max_chars, overlap=overlap,
                                 min_block_chars=min_block)
    idx = build_index(chunks)
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 索引完成：{len(files)} 个文档 → {len(chunks)} 个切片")
    print(f"     参数: max_chars={max_chars}  overlap={overlap}  min_block={min_block}")
    print(f"     平均每片 {sum(len(c['text']) for c in chunks) // max(len(chunks), 1)} 字")
    return 0


def load_index() -> dict:
    if not INDEX.exists():
        print("[!] 还没建索引，先跑: python rag.py --build")
        raise SystemExit(1)
    return json.loads(INDEX.read_text(encoding="utf-8"))


def cmd_ask(q: str, no_llm: bool = False, top_k: int = 3, min_score: float = 0.25):
    idx = load_index()
    hits = search(idx, q, top_k=top_k, min_score=min_score)
    print("=" * 64)
    print(f"问题: {q}")
    print("=" * 64)
    if not hits:
        print("\n[检索] 无结果通过分数门槛 → 触发拒答（这是正确行为，不是 bug）")
        print("\n[回答]")
        print(answer(q, hits, use_llm=False))
        return 0
    print("\n[检索到的资料]")
    for h in hits:
        print(f"  {h['score']:>7}  {h['source']} - {h['title']}")
        print(f"           {h['text'][:100]}...")
    print("\n[回答]")
    print(answer(q, hits, use_llm=not no_llm))
    return 0


def cmd_eval(min_score: float = 0.25):
    """评测集：W03 Day6 任务，必须用实数汇报答对率。

    评测必须包含"不该答的题" —— 只测能答对的题，是在骗自己。
    """
    f = HERE / "eval_questions.jsonl"
    if not f.exists():
        f.write_text(
            "\n".join(json.dumps({"q": q, "expect": e}, ensure_ascii=False) for q, e in [
                ("如何处理客户投诉？", "投诉"),
                ("退款政策是什么？", "退款"),
                ("员工请假怎么申请？", "请假"),
                ("产品保修期多久？", "服务期"),
                ("客户说我们太贵了怎么回？", "贵"),
                ("私有化部署对服务器有什么要求？", "服务器"),
                ("新员工入职需要准备什么材料？", ""),
                ("今天天气怎么样？", ""),
                ("怎么做红烧肉？", ""),
                ("帮我写一首诗", ""),
            ]) + "\n",
            encoding="utf-8",
        )
        print(f"[初始化] {f.name} —— 已生成 10 题（含 4 题不该答的）。你的任务是补到 20 题。")
    idx = load_index()
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    good = bad = refused_ok = refused_bad = 0
    for r in rows:
        hits = search(idx, r["q"], top_k=3, min_score=min_score)
        expect = r.get("expect") or ""
        if expect:                                    # 应该答出来的题
            ok = bool(hits) and any(expect in h["text"] for h in hits)
            good += ok
            bad += not ok
            print(f"  [{'命中' if ok else '未命中'}] {r['q']}")
        else:                                         # 应该拒答的题
            ok = not hits
            refused_ok += ok
            refused_bad += not ok
            print(f"  [{'正确拒答' if ok else '错误作答'}] {r['q']}")
    total = good + bad
    ref_total = refused_ok + refused_bad
    print(f"\n  该答的题命中率: {good}/{total} = {good / max(total, 1):.0%}")
    print(f"  不该答的题拒答率: {refused_ok}/{ref_total} = {refused_ok / max(ref_total, 1):.0%}")
    print("\n⚠️ 两个数字都要看：命中率低=找不到资料；拒答率低=敢瞎编（更危险）。")
    print("   未命中的题就是你产品的护城河所在（W03 商业检查点）。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="企业知识库 Agent（RAG 最小版）")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--ask", metavar="问题")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="只看检索结果，不花钱")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--min-score", type=float, default=0.25,
                    help="相关度绝对下限，低于此值触发拒答（调它看误答怎么变）")
    # 以下三个只对 --build 生效，是 W03 的对照实验参数
    ap.add_argument("--max-chars", type=int, default=400, help="[--build] 每片最长字数")
    ap.add_argument("--overlap", type=int, default=80, help="[--build] 相邻切片重叠字数")
    ap.add_argument("--min-block", type=int, default=120, help="[--build] 碎片合并阈值")
    a = ap.parse_args()
    if a.build:
        return cmd_build(a.max_chars, a.overlap, a.min_block)
    if a.ask:
        return cmd_ask(a.ask, a.no_llm, a.top_k, a.min_score)
    if a.eval:
        return cmd_eval(a.min_score)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
