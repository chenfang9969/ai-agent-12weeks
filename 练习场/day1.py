# -*- coding: utf-8 -*-
r"""练习 1：把"函数"写出来（约 10 分钟）

跑法:  python "D:\DeepSeekHarness\12周计划\练习场\day1.py"

目标：写出 4 个小函数。每个都别超过 10 行。
      你不需要"设计"，只需要把中文要求翻译成 Python。
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# 1. 把摄氏度换成华氏度
#    公式：华氏 = 摄氏 × 9 ÷ 5 + 32
#    例：celsius_to_fahrenheit(100) 应该返回 212.0
# ---------------------------------------------------------------------------
def celsius_to_fahrenheit(c: float) -> float:
    # TODO: 请在这里写（就一行 return）
    return c*9/5+32
    pass


# ---------------------------------------------------------------------------
# 2. 数一句话里有多少个"字"（不含空格）
#    例：count_chars("今天 天气 不错") 应该返回 6
#    提示：可以用 .replace(" ", "") 先把空格去掉，再用 len()
# ---------------------------------------------------------------------------
def count_chars(text: str) -> int:
    # TODO: 请在这里写
    text = text.replace(" ", "")
    return len(text)
    pass


# ---------------------------------------------------------------------------
# 3. 把列表里所有数字加起来，但**跳过负数**
#    例：sum_positive([3, -1, 5, -2, 4]) 应该返回 12
#    提示：一个 for 循环 + 一个 if
# ---------------------------------------------------------------------------
def sum_positive(nums: list[int]) -> int:
    # TODO: 请在这里写
    sum=0
    for i in nums:
        if i>=0:
            sum+=i
    return sum
    pass


# ---------------------------------------------------------------------------
# 4. 给一个名字，返回一段自我介绍（字符串拼接）
#    例：greet("张三") 应该返回 "你好，我是张三，很高兴认识你。"
#    提示：用 f"..." 这种写法
# ---------------------------------------------------------------------------
def greet(name: str) -> str:
    # TODO: 请在这里写
    return f"你好，我是{name}，很高兴认识你。"
    pass


# ===========================================================================
# 下面是测试，不用改。跑这个文件就会自动检查你写得对不对。
# ===========================================================================
def _run_tests() -> int:
    cases = [
        ("celsius_to_fahrenheit(100)", celsius_to_fahrenheit(100), 212.0),
        ("celsius_to_fahrenheit(0)", celsius_to_fahrenheit(0), 32.0),
        ("celsius_to_fahrenheit(37)", celsius_to_fahrenheit(37), 98.6),
        ("count_chars('今天 天气 不错')", count_chars("今天 天气 不错"), 6),
        ("count_chars('abc')", count_chars("abc"), 3),
        ("count_chars('')", count_chars(""), 0),
        ("sum_positive([3,-1,5,-2,4])", sum_positive([3, -1, 5, -2, 4]), 12),
        ("sum_positive([-5,-6])", sum_positive([-5, -6]), 0),
        ("sum_positive([])", sum_positive([]), 0),
        ("greet('张三')", greet("张三"), "你好，我是张三，很高兴认识你。"),
        ("greet('小明')", greet("小明"), "你好，我是小明，很高兴认识你。"),
    ]
    passed = 0
    print("=" * 62)
    print("  练习 1 · 自动批改")
    print("=" * 62)
    for name, got, want in cases:
        if got is None:
            print(f"  [未写] {name}")
            continue
        try:
            ok = abs(got - want) < 1e-6 if isinstance(want, float) else got == want
        except TypeError:
            ok = False
        if ok:
            passed += 1
            print(f"  [通过] {name} = {got}")
        else:
            print(f"  [错误] {name}  ->  你得到 {got!r}，应该是 {want!r}")
    total = len(cases)
    print("-" * 62)
    print(f"  得分: {passed}/{total}")
    if passed == total:
        print("  [完成] 全部通过。今天这块过关了。")
    else:
        print("  [继续] 把标 [未写]/[错误] 的改掉再跑一次。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(_run_tests())
