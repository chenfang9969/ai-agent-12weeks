# -*- coding: utf-8 -*-
"""Day 1：第一次裸调 LLM（无工具、无循环）。

它只证明一件事：key 能用、模型能回话。
用法:  python hello_llm.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import LLMError, chat, estimate_cost, pick_provider  # noqa: E402


def main():
    try:
        p = pick_provider()
    except LLMError as e:
        print(e)
        return 1

    print("=" * 60)
    print(f"供应商: {p.env_var}   模型: {p.model}")
    print("=" * 60)
    print("注意：这里没有工具、没有循环，只是单向问一句。\n")

    r = chat(
        p,
        [
            {"role": "system", "content": "你是商业研究助手，回答简洁、给结论、不说废话。"},
            {"role": "user", "content": "用三句话说明：为什么 LLM 本身不能联网搜索？"},
        ],
        temperature=0.3,
    )
    print(r.text)

    print("\n" + "-" * 60)
    print(f"tokens: 输入 {r.prompt_tokens} / 输出 {r.completion_tokens} "
          f"| 本次成本约 {estimate_cost(p, r.prompt_tokens, r.completion_tokens):.6f} 元")
    print("-" * 60)
    print("""
Day 1 思考题（写进 每日记录/ 的 txt）：
  1. 这次调用里，"智能"体现在哪一行代码？
  2. 如果我让它"查一下今天的新闻"，它能做到吗？为什么？
  3. 要让它能查新闻，我缺的是什么？
-> 答案就是 Agent 存在的理由。
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
