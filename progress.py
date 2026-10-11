# -*- coding: utf-8 -*-
"""12 周计划 · 进度与考核。

职责边界（2026-10-11 重新划分）：
    这个脚本**只考核客观事实**：
      - 每周交付物完成了吗（v0.1 能跑 / Demo / SOP …）
      - 12 周资产推进到哪里了
      - 代码、项目、文档这些"能拿出去给人看的东西"

    它**不考核你的日记**。每日记录是你自己的本子，写什么、写多少、
    写不写，都由你决定。这里不会因为"某天没写"给你标欠账。

用法:
    python progress.py                 # 总览：第几周、资产进度、今天该干什么
    python progress.py --week          # 本周任务卡全文
    python progress.py --check         # 考核：本周交付物状态
    python progress.py --log           # 列出每日记录文件（只看有没有，不评价）
    python progress.py --newday        # 建一个空的今日记录文件（不插问题、不评分）
    python progress.py --asset W01 --proof "项目/xxx/"   # 登记某周交付物完成
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:  # Windows 控制台默认 GBK
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "progress.json"
DAILY = ROOT / "每日记录"
PLANS = ROOT / "周计划"

# WEEKS / START / week_index 统一从 schedule.py 取，避免文案漂移
import schedule as S  # noqa: E402

START = S.START
WEEKS = S.WEEKS
WEEKDAYS = S.WEEKDAYS


def week_index(today: date | None = None) -> int:
    return S.week_index(today or date.today())


DEFAULT = {
    "start_date": START.isoformat(),
    "current_week": 1,
    "daily": {"tech_minutes_target": 60},
    "assets": {w[0]: {"deliverable": w[2], "done": False, "proof": ""} for w in WEEKS},
    "leads": [],
}


def load() -> dict:
    """读取进度。用 utf-8-sig 以兼容被 PowerShell 写入过 BOM 的文件。"""
    if not DATA.exists():
        save(json.loads(json.dumps(DEFAULT)))
        return json.loads(json.dumps(DEFAULT))
    try:
        d = json.loads(DATA.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        print(f"[!] progress.json 解析失败（{e}）。已自动重建，旧文件备份为 progress.json.bak")
        DATA.replace(DATA.with_suffix(".json.bak"))
        save(json.loads(json.dumps(DEFAULT)))
        return json.loads(json.dumps(DEFAULT))
    d.setdefault("assets", {})
    for w in WEEKS:
        d["assets"].setdefault(w[0], {"deliverable": w[2], "done": False, "proof": ""})
    d.setdefault("leads", [])
    d.pop("log", None)          # 早期遗留的死字段：从未被读取，已移除
    return d


def save(d: dict):
    """只在内容真的变了才写盘，避免每次运行都制造无意义的 git 变动。"""
    new = json.dumps(d, ensure_ascii=False, indent=2)
    if DATA.exists() and DATA.read_text(encoding="utf-8-sig") == new:
        return
    DATA.write_text(new, encoding="utf-8")


def bar(done: int, total: int, width: int = 24) -> str:
    fill = int(width * done / max(total, 1))
    return "#" * fill + "." * (width - fill)


def overview(d: dict):
    today = date.today()
    wi = week_index(today)
    code, title, deliverable = WEEKS[wi - 1]
    wk_start = START + timedelta(days=(wi - 1) * 7)
    wk_end = wk_start + timedelta(days=6)
    day_no = (today - wk_start).days + 1
    total_days = (date(2026, 12, 28) - today).days

    done_assets = sum(1 for w in WEEKS if d["assets"].get(w[0], {}).get("done"))

    print("=" * 62)
    print(f"  12周作战进度   |   今天 {today:%Y-%m-%d} 星期{WEEKDAYS[today.weekday()]}")
    print("=" * 62)
    print(f"  当前: 第 {wi} 周  {code} · {title}   (第 {day_no}/7 天)")
    print(f"  周区间: {wk_start:%m-%d} ~ {wk_end:%m-%d}   剩余 {total_days} 天")
    print(f"  周末必须交出: {deliverable}")
    print()
    print(f"  资产完成度 [{bar(done_assets, 12)}] {done_assets}/12")
    print()

    print("  " + "-" * 58)
    print("  12 周轨道")
    print("  " + "-" * 58)
    for i, (c, t, _) in enumerate(WEEKS, 1):
        a = d["assets"].get(c, {})
        mark = "[x]" if a.get("done") else ("[>]" if i == wi else "[ ]")
        flag = "  <== 你现在在这" if i == wi else ""
        print(f"   {mark} {c} {t}{flag}")
    print()

    print("  " + "-" * 58)
    print("  今日动作")
    print("  " + "-" * 58)
    print(f"   任务: {S.task(wi, day_no)}")
    print()
    print("   [ ] 黄金 60 分钟技术块")
    print()
    print("   每日记录是你自己的本子，写什么由你决定（不评分、不计欠账）。")
    print("   想写就开: python today.py")
    print()


def show_week(d: dict):
    wi = week_index()
    code = WEEKS[wi - 1][0]
    cands = sorted(PLANS.glob(f"{code}-*.md")) if PLANS.exists() else []
    if not cands:
        print(f"[!] 还没有 {code} 的任务卡。告诉我：'给我第 {wi} 周任务卡'")
        return
    print(cands[0].read_text(encoding="utf-8"))


def check(d: dict):
    """考核：只认交付物，不看日记。"""
    wi = week_index()
    code, title, deliverable = WEEKS[wi - 1]
    a = d["assets"][code]
    done_assets = sum(1 for w in WEEKS if d["assets"][w[0]].get("done"))

    print("=" * 62)
    print(f"  考核 · {code} {title}")
    print("=" * 62)
    print(f"  本周交付物: {deliverable}")
    print(f"  状态: {'已完成 [OK]' if a.get('done') else '未完成'}")
    print(f"  证据: {a.get('proof') or '（未登记）'}")
    print()
    print(f"  12 周资产: [{bar(done_assets, 12)}] {done_assets}/12")
    print()
    print("  考核只看客观事实：交付物存不存在、能不能跑、有没有证据。")
    print("  每日记录不在考核范围内 —— 那是你自己的东西。")
    if not a.get("done"):
        print()
        print("  完成本周交付物后登记：")
        print(f'    python progress.py --asset {code} --proof "路径或链接"')


def show_log(d: dict):
    """列出最近的记录文件。只看有没有这个文件，不评价内容。"""
    print("=" * 62)
    print("  每日记录（仅列出，不评价）")
    print("=" * 62)
    today = date.today()
    files = sorted(p for p in DAILY.glob("2026-*.txt") if not p.name.startswith("_")) if DAILY.exists() else []
    if not files:
        print("  还没有任何记录文件。")
        return
    for p in files:
        print(f"  {p.stem}   {p.stat().st_size:>6} 字节")
    print()
    print(f"  共 {len(files)} 天有文件。有文件≠写了，写了≠写得好 —— 这些都不考核。")
    st = "已有文件" if (DAILY / f"{today:%Y-%m-%d}.txt").exists() else "还没建"
    print(f"  今天: {st}     想写就: python today.py")


def do_newday():
    """建一个空的今日记录文件。不插问题、不插标记、不评分。"""
    DAILY.mkdir(exist_ok=True)
    today = date.today()
    p = DAILY / f"{today:%Y-%m-%d}.txt"
    wi = week_index(today)
    code, title, deliverable = WEEKS[wi - 1]
    day_no = (today - (START + timedelta(days=(wi - 1) * 7))).days + 1

    if p.exists():
        print(f"[已存在] {p}")
    else:
        p.write_text(
            f"{today:%Y-%m-%d} 星期{WEEKDAYS[today.weekday()]} · {code} Day {day_no}\n"
            f"今日任务：{S.task(wi, day_no)}\n"
            "技术时间：____ 分钟\n\n"
            + "-" * 50 + "\n\n",
            encoding="utf-8",
        )
        print(f"[新建] {p}")
    print("  这是个空本子，想写什么写什么。不评分、不计欠账。")
    return 0


def do_asset(week: str, proof: str | None):
    """登记某周交付物已完成。必须显式指定周次，防止误标当前周。"""
    d = load()
    week = week.upper()
    if not week.startswith("W"):
        week = "W" + week.zfill(2)
    if week not in d["assets"]:
        print(f"[!] 未知周次 {week}，可用: {', '.join(w[0] for w in WEEKS)}")
        return 1
    a = d["assets"][week]
    a["done"] = True
    a["proof"] = proof or a.get("proof") or ""
    save(d)
    done = sum(1 for w in WEEKS if d["assets"][w[0]].get("done"))
    print(f"[OK] {week} 交付物已登记")
    print(f"     交付契约: {a['deliverable']}")
    if not a["proof"]:
        print("     [!] 没填证据。没有证据的交付物不算交付，建议 --proof 补上路径/链接。")
    else:
        print(f"     证据: {a['proof']}")
    print(f"     总进度 [{bar(done, 12)}] {done}/12")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", action="store_true", help="打印本周任务卡")
    ap.add_argument("--check", action="store_true", help="考核：本周交付物状态")
    ap.add_argument("--log", action="store_true", help="列出每日记录文件（不评价）")
    ap.add_argument("--newday", action="store_true", help="建一个空的今日记录文件")
    ap.add_argument("--asset", metavar="W01", help="登记某周交付物完成，例如 --asset W01")
    ap.add_argument("--proof", default=None, help="配合 --asset：证据路径或链接")
    a = ap.parse_args()

    DAILY.mkdir(exist_ok=True)
    if a.asset:
        return do_asset(a.asset, a.proof)
    if a.newday:
        return do_newday()
    d = load()
    save(d)
    if a.week:
        show_week(d)
    elif a.check:
        check(d)
    elif a.log:
        show_log(d)
    else:
        overview(d)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
