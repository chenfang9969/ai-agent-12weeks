# -*- coding: utf-8 -*-
"""W05 · 入口自检 / 回归脚本（录屏前跑一遍，30 秒出结果）

为什么需要它：
    录屏只有一次机会，演示到一半发现接口挂了最贵。
    这个脚本把"必须能答对的问题"和"必须拒答的问题"都列成用例，
    跑一次就知道现在能不能演。

用法:
    python demo_probe.py                      # 默认打 127.0.0.1:8100
    python demo_probe.py --base-url http://127.0.0.1:8200
    python demo_probe.py --verbose            # 打印每个答案的开头

判定:
    hit    → 必须返回 refused=false 且至少 1 条来源
    refuse → 必须返回 refused=true（不编造，这是产品承诺）
    只比"答不答"，不比措辞 —— 措辞每次都不一样，拿它当断言会天天红。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (问题, 期望, 备注)
CASES: list[tuple[str, str, str]] = [
    ("客户投诉怎么处理？", "hit", "培训文档·五步流程"),
    ("客户说AI答不准怎么办？", "hit", "销售资料·异议三"),
    ("软件服务期多久？", "hit", "产品资料·保修与售后"),
    ("私有化部署要什么服务器？", "hit", "产品资料·部署方式"),
    ("基础版多少钱？", "hit", "产品资料·价格方案"),
    ("怎么申请报销？", "hit", "员工手册·报销"),
    ("今天上海天气怎么样？", "refuse", "知识库外的问题"),
    ("你们能帮我写一份劳动合同吗？", "refuse", "越界请求"),
]


def ask(base: str, q: str, timeout: int = 120) -> tuple[dict, float]:
    body = json.dumps({"question": q, "top_k": 3, "min_score": 0.25},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/api/ask", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")), time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8100")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print(f"  W05 入口自检 · {a.base_url}")
    print("=" * 78)

    passed = failed = 0
    worst = 0.0
    for q, expect, note in CASES:
        try:
            d, dt = ask(a.base_url, q)
        except urllib.error.HTTPError as e:
            print(f"[FAIL] {q}  HTTP {e.code}")
            failed += 1
            continue
        except Exception as e:  # 连不上 / 超时
            print(f"[FAIL] {q}  {type(e).__name__}: {e}")
            failed += 1
            continue

        worst = max(worst, dt)
        ok = bool(d["refused"] is False and d["sources"]) if expect == "hit" \
            else d["refused"] is True
        tag = "PASS" if ok else "FAIL"
        passed += ok
        failed += (not ok)
        sc = ",".join(f"{s['score']:.2f}" for s in d["sources"]) or "-"
        print(f"[{tag}] {q}")
        print(f"       {note} · mode={d['mode']} · 来源 {len(d['sources'])} 段 ({sc}) · {dt:.1f}s")
        if a.verbose or not ok:
            print("       答: " + " ".join(d["answer"].split())[:120])

    print("-" * 78)
    print(f"  通过 {passed} / {passed + failed} · 最慢一次 {worst:.1f}s")
    print(f"  录屏建议：只挑 PASS 的前 3 条，再加 1 条'必须拒答'的")
    print("=" * 78)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
