# -*- coding: utf-8 -*-
"""12 周计划进度指挥官。

用法:
    python progress.py            # 总览：现在第几周、今天该干什么
    python progress.py --week     # 本周任务卡全文
    python progress.py --check    # 体检：本周资产是否欠账
    python progress.py --log      # 看每天记录写了没有（断更预警）
    python progress.py --checkin  # 今日打卡：创建/检查今天的记录文件
    python progress.py --asset W01 --proof "项目/ai-research-agent/"   # 登记某周资产完成
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
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
    "daily": {"tech_minutes_target": 60, "log_minutes_target": 30},
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
        print(f"[!] progress.json 解析失败（{e}）。已自动重建为默认值，旧文件备份为 progress.json.bak")
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
    """只在内容真的变了才写盘。

    否则每次跑 progress.py 都会重写文件、制造无意义的 git 变动。
    """
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
    logs = {p.stem for p in DAILY.glob("*.txt")} if DAILY.exists() else set()
    streak = 0
    cur = today
    while cur.strftime("%Y-%m-%d") in logs:
        streak += 1
        cur -= timedelta(days=1)

    print("=" * 62)
    print(f"  12周作战进度   |   今天 {today:%Y-%m-%d} 星期{'一二三四五六日'[today.weekday()]}")
    print("=" * 62)
    print(f"  当前: 第 {wi} 周  {code} · {title}   (第 {day_no}/7 天)")
    print(f"  周区间: {wk_start:%m-%d} ~ {wk_end:%m-%d}   剩余 {total_days} 天")
    print(f"  周末必须交出: {deliverable}")
    print()
    print(f"  资产完成度 [{bar(done_assets, 12)}] {done_assets}/12")
    print(f"  连续记录天数: {streak} 天" + ("   <- 断更了，今天必须补" if streak == 0 else ""))
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
    print("   [ ] 1. 黄金 60 分钟：只做本周任务卡里的当天 3 步")
    print("   [ ] 2. 30 分钟记录：理解了什么/解决了什么/商业价值/客户场景")
    print("   [ ] 3. 5 分钟：写下明天第一件事")
    print(f"   记录文件: 每日记录\\{today:%Y-%m-%d}.txt")
    print()


def show_week(d: dict):
    wi = week_index()
    code = WEEKS[wi - 1][0]
    cands = sorted(PLANS.glob(f"{code}-*.md")) if PLANS.exists() else []
    if not cands:
        print(f"[!] 还没有 {code} 的任务卡。告诉你的监督者（我）：'给我第 {wi} 周任务卡'。")
        return
    print(cands[0].read_text(encoding="utf-8"))


TEMPLATE_SIZE = 417      # 打卡脚本生成的纯模板正文长度

# 记录里必须回答的四个反思题（对应原计划的"每天 30 分钟记录"）
REFLECT_KEYS = ["【1】", "【2】", "【3】", "【4】"]
ANSWER_OPEN = "===== 你的答案 ====="
ANSWER_CLOSE = "===== 结束 ====="


def _answer_chars(seg: str) -> int:
    """只统计 "===== 你的答案 =====" 与 "===== 结束 =====" 之间的内容。

    为什么用标记而不是猜：**提示和答案混在同一个文件里时，任何启发式都会误判。**
    实测教训：先按"行首是否'提示：'"过滤 → 仍把示范文和提示正文算成答案；
    再按字数阈值 → 45 字和 200 字的提示都过不了关但会被算进某些题。
    让写的人明确划出答案区，是最可靠也最省事的办法。
    """
    total = 0
    in_answer = False
    for line in seg.splitlines():
        s = line.strip()
        if s.startswith(ANSWER_OPEN):
            in_answer = True
            continue
        if s.startswith(ANSWER_CLOSE):
            in_answer = False
            continue
        if in_answer and s:
            total += len(s)
    return total


def reflect_answers(path: Path) -> list[tuple[str, int]]:
    """检查四个反思题各写了多少字实质内容（排除提示行）。

    为什么必须这么查：**文件存在 ≠ 你写了。**
    打卡脚本会生成模板，字节数也够长，光看长度会给出虚假的安心。
    """
    if not path.exists():
        return [(k, 0) for k in REFLECT_KEYS]
    text = path.read_text(encoding="utf-8", errors="ignore")
    out: list[tuple[str, int]] = []
    for i, key in enumerate(REFLECT_KEYS):
        start = text.find(key)
        if start < 0:
            out.append((key, 0))
            continue
        end = text.find(REFLECT_KEYS[i + 1], start) if i + 1 < len(REFLECT_KEYS) else len(text)
        out.append((key, _answer_chars(text[start:end])))
    return out


ANSWER_MIN_CHARS = 20    # 单题实质作答至少这么多字，否则算没答


def check(d: dict):
    wi = week_index()
    code, title, deliverable = WEEKS[wi - 1]
    a = d["assets"][code]
    print("=" * 62)
    print(f"  体检报告 · {code} {title}")
    print("=" * 62)
    print(f"  本周交付契约: {deliverable}")
    print(f"  状态: {'已完成 [OK]' if a.get('done') else '未完成 [欠账]'}")
    if a.get("proof"):
        print(f"  证据: {a['proof']}")
    print()

    if not DAILY.exists():
        print("  [!] 每日记录目录都不存在 —— 今天是第 1 天，正常。")
        return
    wk_start = START + timedelta(days=(wi - 1) * 7)
    missing, thin = [], []
    for i in range(7):
        day = wk_start + timedelta(days=i)
        if day > date.today():
            break
        p = DAILY / f"{day:%Y-%m-%d}.txt"
        tag = f"{day:%m-%d}({'一二三四五六日'[day.weekday()]})"
        if not p.exists():
            missing.append(tag)
            continue
        answered = sum(1 for _, c in reflect_answers(p) if c >= ANSWER_MIN_CHARS)
        if answered < 4:
            thin.append(f"{tag} 只答了 {answered}/4 题")

    # ★ 关键：文件存在 ≠ 你写了。没答四个反思题就等于没记录。
    if missing:
        print(f"  [欠] 完全没有记录的日期: {', '.join(missing)}")
    if thin:
        print(f"  [半成品] 记录存在但反思题没答完的:")
        for t in thin:
            print(f"           - {t}")
        print("           → 存在 ≠ 写了。这四个问题是这 30 分钟的全部价值。")
    if not missing and not thin:
        print("  [OK] 本周记录齐全，且四个反思题都答了。")

    print()
    print("  每周最后一天（周日 21:00）必须回答：")
    print("   1. 本周新增能力？")
    print("   2. 产生什么资产？（文件/代码/文档/视频/联系人 —— 没有资产=这周白过）")
    print("   3. 距离赚钱更近了吗？")
    print(f"   记录到: 周复盘\\{code}-复盘.md")


def show_log(d: dict):
    print("=" * 62)
    print("  记录断更检查（最近 10 天）")
    print("=" * 62)
    today = date.today()
    for i in range(9, -1, -1):
        day = today - timedelta(days=i)
        if day < START:
            continue
        p = DAILY / f"{day:%Y-%m-%d}.txt"
        if p.exists():
            n = len(p.read_text(encoding="utf-8").strip())
            ans = sum(1 for _, c in reflect_answers(p) if c >= ANSWER_MIN_CHARS)
            note = "" if ans == 4 else f"  <- 反思题只答 {ans}/4"
            print(f"  [x] {day:%m-%d}  {n} 字{note}")
        else:
            tag = "  <- 今天，还没写" if day == today else ""
            print(f"  [ ] {day:%m-%d}  未记录{tag}")
    print()
    # 空壳也算欠账：文件存在不代表写了。
    # 注意：只统计"计划已开始且已经过去"的天数 —— 把未来天数算成"完整记录"是错的。
    bad, elapsed = [], 0
    for i in range(10):
        day = today - timedelta(days=i)
        if day < START:
            break
        elapsed += 1
        p = DAILY / f"{day:%Y-%m-%d}.txt"
        if not p.exists() or sum(1 for _, c in reflect_answers(p) if c >= ANSWER_MIN_CHARS) < 4:
            bad.append(day)
    if elapsed == 0:
        print("  [i] 计划还没开始。")
    elif len(bad) >= 3:
        print(f"  [!!] 最近 {elapsed} 天里有 {len(bad)} 天没有完整记录。纪律涣散，立即恢复节奏。")
    elif len(bad) == 0:
        print(f"  [OK] 已开始的 {elapsed} 天全部有完整记录。保持住。")
    else:
        print(f"  [!] 已开始的 {elapsed} 天里，{len(bad)} 天记录不完整："
              + ", ".join(f"{d:%m-%d}" for d in bad))


def do_checkin():
    """今日打卡：创建/补全今天的记录文件。"""
    DAILY.mkdir(exist_ok=True)
    today = date.today()
    p = DAILY / f"{today:%Y-%m-%d}.txt"
    wi = week_index(today)
    code, title, _ = WEEKS[wi - 1]
    wk_start = START + timedelta(days=(wi - 1) * 7)
    day_no = (today - wk_start).days + 1

    if p.exists():
        print(f"[已存在] {p}")
        n = len(p.read_text(encoding="utf-8"))
        print(f"   当前 {n} 字。把它填完整再回来。")
    else:
        BLOCK = "===== 你的答案 =====\n\n===== 结束 =====\n"
        p.write_text(
            f"日期：{today:%Y-%m-%d}（星期{'一二三四五六日'[today.weekday()]}）· "
            f"{code} Day {day_no}\n"
            f"当天任务卡：{title}（见 12周总任务卡）\n"
            "实际投入技术时间：____ 分钟\n\n"
            "规则：把答案写在 ===== 你的答案 ===== 与 ===== 结束 ===== 之间。\n"
            "      写在标记外的不算（我也检测不到）。\n\n"
            "--------------------------------------------------\n"
            "【1】今天理解了什么？\n" + BLOCK + "\n"
            "【2】今天解决了什么问题？\n" + BLOCK + "\n"
            "【3】这个技术有什么商业价值？\n" + BLOCK + "\n"
            "【4】有没有客户场景？是谁？他会为什么付钱？\n" + BLOCK + "\n"
            "--------------------------------------------------\n"
            "【明日第一件事】\n\n"
            "【今日状态】1-10 分：\n"
            "【今日一句话】\n",
            encoding="utf-8",
        )
        print(f"[新建] {p}")
        print("   把答案写在 ===== 你的答案 ===== 与 ===== 结束 ===== 之间。")
        print("   写完跑一次:  python progress.py --check   （会告诉你答了几题）")

    # 打卡后给出真实进度：答了几题，以及连续记录天数
    answered = sum(1 for _, c in reflect_answers(p) if c >= ANSWER_MIN_CHARS)
    print(f"\n   反思题进度: {answered}/4 题已作答"
          + ("   全部完成，很好。" if answered == 4 else "   把答案写在 ===== 你的答案 ===== 与 ===== 结束 ===== 之间。"))

    logs = {q.stem for q in DAILY.glob("*.txt")}
    streak = 0
    cur = today
    while cur.strftime("%Y-%m-%d") in logs:
        streak += 1
        cur -= timedelta(days=1)
    print(f"   连续记录: {streak} 天")
    return 0


def do_asset(week: str, proof: str | None):
    """登记某周资产已完成。必须显式指定周次，防止误标当前周。"""
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
    wi = week_index()
    print(f"[OK] {week} 资产已登记为完成")
    print(f"     交付契约: {a['deliverable']}")
    if not a["proof"]:
        print("     [!] 没填证据。没有证据的资产不算资产，建议 --proof 补上路径/链接。")
    else:
        print(f"     证据: {a['proof']}")
    print(f"     总进度 [{bar(done, 12)}] {done}/12")
    if week == WEEKS[wi - 1][0] and (date.today() - (START + timedelta(days=(wi - 1) * 7))).days < 6:
        print("     [!] 注意：本周才过了不到 6 天，你确认真做完了？虚报进度骗的是自己。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", action="store_true", help="打印本周任务卡")
    ap.add_argument("--check", action="store_true", help="本周体检")
    ap.add_argument("--log", action="store_true", help="记录断更检查")
    ap.add_argument("--checkin", action="store_true", help="今日打卡（创建记录文件）")
    ap.add_argument("--asset", metavar="W01",
                    help="登记某周资产完成，必须显式写周次，例如 --asset W01")
    ap.add_argument("--proof", default=None, help="配合 --asset：证据路径或链接")
    a = ap.parse_args()
    DAILY.mkdir(exist_ok=True)
    if a.asset:
        return do_asset(a.asset, a.proof)
    if a.checkin:
        return do_checkin()
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
