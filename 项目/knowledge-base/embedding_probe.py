"""Embedding 探针：验证「向量检索」能不能救回「保修期 vs 服务期」这题。

用法（PowerShell）：
    $env:SILICONFLOW_API_KEY = "你的key"
    python embedding_probe.py

它做三件事：
  1. 用和你 rag.py 一模一样的切法切同一批资料
  2. 用词频（你现在的方法）排一次名
  3. 用 bge-m3 向量（embedding）再排一次名
  4. 把两次的排名并排打出来 —— 一眼看出 embedding 有没有用

不需要装任何依赖，只用标准库。
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

API_URL = "https://api.siliconflow.cn/v1/embeddings"
MODEL = "BAAI/bge-m3"          # 注意：不要填 Pro/BAAI/bge-m3，那个收费

QUERY = "产品保修期多久？"


# --------------------------------------------------------------------------
# 1. 切块：直接复用 rag.py，保证和你现在的方法完全一致
# --------------------------------------------------------------------------
def load_chunks() -> list[dict]:
    sys.path.insert(0, str(HERE))
    from rag import split_markdown

    chunks: list[dict] = []
    for p in sorted(DATA.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        chunks.extend(split_markdown(text, p.name, max_chars=400, overlap=80))
    return chunks


# --------------------------------------------------------------------------
# 2. 调 SiliconFlow 拿向量
# --------------------------------------------------------------------------
def embed(texts: list[str], key: str) -> list[list[float]]:
    body = json.dumps({
        "model": MODEL,
        "input": texts,
        "encoding_format": "float",
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:600]
        raise SystemExit(
            f"\n[调用失败] HTTP {e.code}\n{detail}\n\n"
            "常见原因：\n"
            "  - 401/403：API Key 错了或没实名\n"
            "  - 404：模型名写错（必须是 BAAI/bge-m3，不能带 Pro/）\n"
            "  - 429：免费额度被限流，等一分钟再试\n"
        ) from None
    except urllib.error.URLError as e:
        raise SystemExit(f"\n[网络失败] {e.reason}\n可能是代理/VPN 问题，先确认能访问 siliconflow.cn\n") from None

    items = sorted(data["data"], key=lambda x: x["index"])
    return [it["embedding"] for it in items]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------
# 3. 主流程
# --------------------------------------------------------------------------
def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="对比词频检索与向量检索")
    ap.add_argument("--rerank", action="store_true",
                    help="在向量召回之后再跑一遍 LLM 精排（需要 DEEPSEEK_API_KEY）")
    ap.add_argument("--top-n", type=int, default=6,
                    help="交给 LLM 精排的候选数（默认 6）")
    args = ap.parse_args()

    key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "没读到 SILICONFLOW_API_KEY。\n"
            "在 PowerShell 里先设：$env:SILICONFLOW_API_KEY = \"你的key\"\n"
        )

    chunks = load_chunks()
    print("=" * 78)
    print(f"  问题：{QUERY}")
    print(f"  切出 {len(chunks)} 段（和 rag.py 同一套参数）")
    print("=" * 78)

    # --- 词频排名（你现在的方法）---
    from rag import build_index, search

    k_index = build_index(chunks)
    # 门槛全开，拿到完整排名（默认 0.25/0.45 会把低分的直接过滤掉）
    k_hits = search(k_index, QUERY, top_k=len(chunks), min_score=0.0, rel_threshold=0.0)
    k_rank = {h["id"]: (i + 1, h["score"]) for i, h in enumerate(k_hits)}

    # --- 向量排名 ---
    print("\n正在调用 bge-m3 向量化 …")
    vecs = embed([QUERY] + [c["text"] for c in chunks], key)
    q_vec, c_vecs = vecs[0], vecs[1:]
    sims = [cosine(q_vec, v) for v in c_vecs]
    order = sorted(range(len(chunks)), key=lambda i: -sims[i])

    # --- 并排打印 ---
    print()
    print("=" * 78)
    print("  排名对比（只看有没有把「保修与售后」那段排上来）")
    print("=" * 78)
    for rank, i in enumerate(order[:6], 1):
        c = chunks[i]
        kw_rank, kw_score = k_rank.get(c["id"], (999, 0.0))
        mark = "★" if "服务期" in c["text"] else " "
        print(f"\n  {mark} 向量第 {rank} 名 | 词频第 {kw_rank} 名")
        print(f"    来源: {c['source']} / {c['title']}")
        print(f"    向量相似度: {sims[i]:.4f}   词频分: {kw_score:.4f}")
        snippet = c["text"].replace("\n", " ")[:90]
        print(f"    内容: {snippet}…")

    # --- 判定 ---
    target = next((i for i, c in enumerate(chunks) if "服务期以购买年限为准" in c["text"]), None)
    print()
    print("=" * 78)
    if target is None:
        print("  ⚠️ 没找到含「服务期以购买年限为准」的段落，检查 data/ 是否完整")
    else:
        v_pos = order.index(target) + 1
        k_pos = k_rank.get(chunks[target]["id"], (999, 0.0))[0]
        print(f"  含正确答案那段（「服务期以购买年限为准」）：")
        print(f"    词频排名: 第 {k_pos} 名   ← 你现在的方法")
        print(f"    向量排名: 第 {v_pos} 名   ← embedding")
        if v_pos <= 3:
            print("\n  ✅ 结论：embedding 把它救进了 top-3，能答出这道题了。")
        elif v_pos < k_pos:
            print("\n  ⚠️ 结论：embedding 有提升，但还没进 top-3，需要再调（换模型 / 加 rerank）。")
        else:
            print("\n  ❌ 结论：embedding 没救回来。这说明问题不在检索方式，在别处。")
    print("=" * 78)
    print("\n把上面这段输出发我，我更新对照表。")

    # --- 可选的第三段：LLM 精排 ---
    if args.rerank:
        from rerank_test import rerank

        top_n = args.top_n
        cands = [
            {**chunks[i], "vec_score": round(sims[i], 4)}
            for i in order[:top_n]
        ]
        print()
        print("=" * 78)
        print(f"  LLM 精排（拿向量 top-{top_n} 交给模型打分，keep=3 / 门槛 5 分）")
        print("=" * 78)
        try:
            kept = rerank(QUERY, cands, keep=3, min_score=5)
        except Exception as e:                      # 没配 LLM Key 也不要崩
            print(f"\n  [精排失败] {e}")
            print("  检查 项目/ai-research-agent/.env 里的 DEEPSEEK_API_KEY")
            return

        if not kept:
            print("\n  (全部被过滤 —— 等于拒答，宁少勿滥)")
        for rank, h in enumerate(kept, 1):
            mark = "★" if "服务期" in h["text"] else " "
            print(f"\n  {mark} 精排第 {rank} 名 | LLM={h['llm_score']} 分 | 向量 {h['vec_score']:.4f}")
            print(f"    来源: {h['source']} / {h['title']}")
            print(f"    内容: {h['text'].replace(chr(10), ' ')[:80]}…")

        if target is not None:
            kept_ids = [h["id"] for h in kept]
            ok = chunks[target]["id"] in kept_ids
            print()
            print(f"  含答案那段最终: {'✅ 保留（能答了）' if ok else '❌ 被精排扔掉（仍答不出）'}")
        print("=" * 78)


if __name__ == "__main__":
    main()
