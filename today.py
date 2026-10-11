# -*- coding: utf-8 -*-
r"""打开今天的记录本。

用法:
    python "D:\DeepSeekHarness\12周计划\today.py"        # 建好并打开今天的
    python "D:\DeepSeekHarness\12周计划\today.py" --path # 只打印路径
    python "D:\DeepSeekHarness\12周计划\today.py" --dir  # 打开记录文件夹

说明（2026-10-11 改）:
    这**不是打卡**，也没有任何评分。
    它只是帮你把今天的文件建好、用记事本打开，省得你翻路径。
    写什么、写多少、写不写，都是你自己的事。
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
    ap = argparse.ArgumentParser(description="打开今天的记录本")
    ap.add_argument("--path", action="store_true", help="只打印文件路径")
    ap.add_argument("--dir", action="store_true", help="打开记录文件夹")
    a = ap.parse_args()

    P.DAILY.mkdir(parents=True, exist_ok=True)

    if a.dir:
        subprocess.Popen(["explorer", str(P.DAILY)])
        print(f"[已打开文件夹] {P.DAILY}")
        return 0

    P.do_newday()
    path = P.DAILY / f"{P.date.today():%Y-%m-%d}.txt"

    print()
    print("=" * 62)
    print("  文件路径:")
    print(f"  {path}")
    print("=" * 62)

    if not path.exists():
        print("  [异常] 文件没能创建。请把这一屏截图发我。")
        return 1
    if a.path:
        return 0

    try:
        subprocess.Popen(["notepad", str(path)])
        print("  [已用记事本打开]")
        print("  写完按 Ctrl+S 保存。（记事本不会自动保存，这是它的老毛病）")
    except Exception as e:
        print(f"  [打开失败] {type(e).__name__}: {e}")
        print("  手动打开上面那个路径即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
