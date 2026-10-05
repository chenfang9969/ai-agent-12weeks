# -*- coding: utf-8 -*-
"""AI 商业研究助手 v0.1 —— 命令行入口

用法:
    python main.py "分析字节跳动的AI战略"
    python main.py "分析某公司AI战略" --steps 6
    python main.py "某主题" --steps 2      # 对照实验：看步数不够时质量怎么塌
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import LLMError  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="AI 商业研究助手 v0.1")
    ap.add_argument("topic", nargs="?", default="分析某公司AI战略", help="研究主题")
    ap.add_argument("--steps", type=int, default=10, help="最大循环步数（试试改成 2 看效果）")
    ap.add_argument("--temp", type=float, default=0.3)
    ap.add_argument("--quiet", action="store_true", help="不打印过程")
    args = ap.parse_args()

    try:
        from agent import ResearchAgent
        bot = ResearchAgent(max_steps=args.steps, temperature=args.temp, verbose=not args.quiet)
    except LLMError as e:
        print(e)
        return 1

    t0 = time.time()
    report = bot.research(args.topic)
    cost_s = time.time() - t0

    out = Path(__file__).resolve().parent / "output"
    out.mkdir(exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "-", args.topic)[:50]
    path = out / f"{datetime.now():%Y%m%d}-{safe}.md"

    header = (
        f"<!-- AI商业研究助手 v0.1 | {datetime.now():%Y-%m-%d %H:%M} "
        f"| model={bot.provider.model} steps={args.steps} "
        f"耗时={cost_s:.0f}s tokens={bot.prompt_tokens + bot.completion_tokens} "
        f"成本≈{bot.cost:.4f}元 -->\n\n"
    )
    path.write_text(header + report, encoding="utf-8")

    print("\n" + "=" * 64)
    print(f"报告已生成: {path}")
    print(f"耗时 {cost_s:.0f}s | 工具调用 {sum(1 for x in bot.log if x['role'] == 'tool')} 次 "
          f"| tokens {bot.prompt_tokens + bot.completion_tokens} | 成本≈{bot.cost:.4f} 元")
    print("=" * 64)
    print("""
今日必答（写进 每日记录/ 的 txt）：
  1. 报告里哪些内容是模型编的？怎么发现的？
  2. 这份报告省了我多少时间？
  3. 谁会为"自动出研究报告"付钱？写下具体一个名字。
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
