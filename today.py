# -*- coding: utf-8 -*-
r"""打开今天的记录文件 —— 省得你再打长路径。

用法:
    python "D:\DeepSeekHarness\12周计划\today.py"        # 建好并打开今天的记录
    python "D:\DeepSeekHarness\12周计划\today.py" --path  # 只打印路径，不打开
    python "D:\DeepSeekHarness\12周计划\today.py" --dir   # 打开记录文件夹

为什么有这个脚本：
    直接跑 progress.py --checkin 会建文件，但输出里路径混在提示文字中间，
    容易看漏。这个脚本只做一件事：把文件建好、用记事本打开、路径单独一行打印。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import progress as P  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="打开今天的每日记录")
    ap.add_argument("--path", action="store_true", help="只打印文件路径")
    ap.add_argument("--dir", action="store_true", help="打开记录文件夹")
    a = ap.parse_args()

    P.DAILY.mkdir(parents=True, exist_ok=True)

    if a.dir:
        subprocess.Popen(["explorer", str(P.DAILY)])
        print(f"[已打开文件夹] {P.DAILY}")
        return 0

    # 静默建文件（复用 progress 的 checkin 逻辑，但不打印它那一堆提示）
    before = set(P.DAILY.glob("*.txt"))
    P.do_checkin()
    after = set(P.DAILY.glob("*.txt"))

    today = P.date.today()
    path = P.DAILY / f"{today:%Y-%m-%d}.txt"

    print()
    print("=" * 64)
    print("  文件路径（复制这行也行）:")
    print(f"  {path}")
    print("=" * 64)

    if not path.exists():
        print("  [异常] 文件没能创建。请把这个界面截图发给我。")
        return 1

    if path in after - before:
        print("  [新建] 今天的记录文件已创建。")
    else:
        answered = sum(1 for _, c in P.reflect_answers(path) if c >= P.ANSWER_MIN_CHARS)
        print(f"  [已存在] 反思题进度: {answered}/4")

    if a.path:
        return 0

    try:
        subprocess.Popen(["notepad", str(path)])
        print("  [已用记事本打开] 写完 Ctrl+S 保存即可。")
    except Exception as e:
        print(f"  [打开失败] {type(e).__name__}: {e}")
        print("  手动打开上面那个路径即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
