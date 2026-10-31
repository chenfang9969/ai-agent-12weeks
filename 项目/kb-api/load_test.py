# -*- coding: utf-8 -*-
"""W05 · 全链路压测（D6）：并发、慢网、超长输入、降级模式

要回答的问题不是"最快多少"，而是"**几个人同时问会开始变慢/报错**"。
这个脚本只用标准库，输出 p50 / p95 / 最大耗时和失败原因。

用法:
    python load_test.py                          # 3 并发 × 3 轮
    python load_test.py --concurrency 10 --rounds 2
    python load_test.py --no-llm                 # 只打检索模式（模拟没用 Key）
    python load_test.py --question "客户投诉怎么处理？"

判定标准（W05 自己定的）:
    3 并发  p95 < 5s        → 能演示
    10 并发 p95 < 15s 且无 5xx → 能小团队试跑
    有 5xx 或拒答异常        → 必须记崩溃点
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIX = [
    "客户投诉怎么处理？",
    "客户说AI答不准怎么办？",
    "软件服务期多久？",
    "私有化部署要什么服务器？",
    "基础版多少钱？",
    "怎么申请报销？",
    "年假怎么休？",
    "客户要退款怎么办？",
]
LONG = "我想了解一下你们产品的整体情况，" * 18  # 约 500 字边界


def one(base: str, q: str, no_llm: bool, timeout: float = 120) -> dict:
    body = json.dumps({"question": q, "top_k": 3, "min_score": 0.25, "no_llm": no_llm},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/api/ask", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {"ok": True, "ms": (time.time() - t0) * 1000, "status": r.status,
                "refused": d["refused"], "mode": d["mode"], "src": len(d["sources"]), "q": q}
    except urllib.error.HTTPError as e:
        return {"ok": False, "ms": (time.time() - t0) * 1000, "status": e.code,
                "err": e.read().decode("utf-8", "replace")[:80], "q": q}
    except Exception as e:
        return {"ok": False, "ms": (time.time() - t0) * 1000, "status": 0,
                "err": f"{type(e).__name__}: {e}", "q": q}


def run(base: str, questions: list[str], concurrency: int, no_llm: bool, label: str) -> list[dict]:
    print(f"\n[{label}] 并发 {concurrency} · 请求 {len(questions)} 条 · no_llm={no_llm}")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        res = list(ex.map(lambda q: one(base, q, no_llm), questions))
    wall = time.time() - t0
    lat = sorted(r["ms"] for r in res if r["ok"])
    errs = [r for r in res if not r["ok"]]
    if lat:
        p50 = statistics.median(lat)
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
        print(f"  成功 {len(lat)}/{len(res)} · p50 {p50/1000:.2f}s · p95 {p95/1000:.2f}s · max {max(lat)/1000:.2f}s · 总墙钟 {wall:.2f}s")
        print(f"  模式: {sorted({r['mode'] for r in res if r['ok']})} · 拒答 {sum(1 for r in res if r['ok'] and r['refused'])} 条")
    for e in errs:
        print(f"  [FAIL] {e.get('status')} {e.get('err')} | {e['q'][:20]}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8100")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--question", default="")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print(f"  W05 压测 · {a.base_url}")
    print("=" * 78)

    # 场景 1：同一问题 × N（最坏情况：模型对同一 prompt，可能命中限流）
    q1 = a.question or "客户投诉怎么处理？"
    run(a.base_url, [q1] * a.concurrency, a.concurrency, a.no_llm, "场景1 同一问题并发")

    # 场景 2：混合问题
    mix = (MIX * ((a.concurrency * a.rounds // len(MIX)) + 1))[: a.concurrency * a.rounds]
    run(a.base_url, mix, a.concurrency, a.no_llm, "场景2 混合问题")

    # 场景 3：超长输入（约 500 字，边界）
    run(a.base_url, [LONG] * a.concurrency, a.concurrency, a.no_llm, "场景3 超长输入(≈500字)")

    # 场景 4：降级模式（模拟没有 Key）
    run(a.base_url, (MIX * 3)[: a.concurrency * 2], a.concurrency, True, "场景4 检索模式(无Key)")

    print("\n" + "=" * 78)
    print("  记下 p95 和失败原因 —— 那就是你以后对客户承诺的边界。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
