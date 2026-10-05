# -*- coding: utf-8 -*-
"""每日提醒 —— 让"我每天提醒你"这件事真的能落地。

数据来源：schedule.py（唯一数据源）。任务文案只在那里定义一次，
本文件不再重复维护，避免"提醒说的和任务卡写的"不一致。

为什么用 Python 写：PowerShell 5.1 无 BOM 时按 GBK 读 .ps1，中文必乱码。
Python 能自己控制编码，文案才不会变成天书。

用法:
    python reminder.py                    # 控制台提醒 + 尝试弹窗
    python reminder.py --no-popup         # 只要控制台
    python reminder.py --date 2026-10-20  # 指定日期（测试用）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DAILY = ROOT / "每日记录"
START = date(2026, 10, 6)
WEEKDAYS = "一二三四五六日"

import schedule as S  # noqa: E402


def overdue_days(today: date) -> list[str]:
    """最近 7 天内缺记录的日子（跨周也照样算，不许用周界掩盖欠账）。"""
    missing: list[str] = []
    for i in range(7):
        d = today - timedelta(days=i)
        if d < START:
            break
        if not (DAILY / f"{d:%Y-%m-%d}.txt").exists():
            missing.append(f"{d:%m-%d}")
    return missing


def build_message(today: date) -> tuple[str, str, str]:
    """返回 (控制台全文, 通知标题, 通知正文)。"""
    wi = S.week_index(today)
    code, title, deliverable = S.WEEKS[wi - 1]
    day_no = (today - S.week_start(wi)).days + 1
    task = S.task(wi, day_no)

    missing = overdue_days(today)
    if not missing:
        warn = "记录无欠账，保持住。"
    elif len(missing) <= 2:
        warn = f"欠 {len(missing)} 天记录：{', '.join(missing)}"
    else:
        warn = f"!! 欠 {len(missing)} 天记录（{', '.join(missing)}）—— 今天必须补"

    tf = DAILY / f"{today:%Y-%m-%d}.txt"
    words = len(tf.read_text(encoding="utf-8")) if tf.exists() else 0

    dash = "=" * 58
    lines = [
        "",
        dash,
        f"  12周计划 · 每日提醒    {today:%Y-%m-%d} 星期{WEEKDAYS[today.weekday()]}",
        dash,
        f"  当前: 第 {wi} 周 {code} · {title}   (第 {day_no}/7 天)",
        "",
        f"  今日任务: {task}",
        "",
        "  [ ] 黄金 60 分钟技术块",
        "  [ ] 30 分钟记录：理解了什么 / 解决了什么 / 商业价值 / 客户场景",
        "  [ ] 5 分钟：写下明天第一件事",
        "",
        f"  本周交付: {deliverable}",
        f"  今日记录: {words} 字    {warn}",
        "",
        f'  打卡:   python "{ROOT}\\progress.py" --checkin',
        f'  日历:   python "{ROOT}\\schedule.py" --week {wi}',
        dash,
    ]
    console = "\n".join(lines)
    return console, f"12周计划 · 第{wi}周第{day_no}天", f"{task}\n{warn}"


def popup(title: str, message: str) -> bool:
    """弹窗三级降级：BurntToast（桌面通知，计划任务也能显示）→ WinForms 气泡 → 提示音。

    ⚠️ 重要技术真相：Windows 计划任务运行在会话 0，**它的控制台窗口用户看不见**。
    所以对"定时提醒"来说，桌面通知（Toast）才是主路径，控制台只是兜底。
    """
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Import-Module BurntToast -ErrorAction SilentlyContinue;"
        "if(-not (Get-Module BurntToast)){"
        "  try{"
        "    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue;"
        "    Install-Module BurntToast -Scope CurrentUser -Force -AllowClobber -ErrorAction Stop;"
        "    Import-Module BurntToast -ErrorAction Stop"
        "  }catch{}"
        "}"
        "$t=$env:DSH_POPUP_TITLE; $m=$env:DSH_POPUP_MSG;"
        "try{"
        "  if(Get-Module BurntToast){"
        "    New-BurntToastNotification -Text $t,$m | Out-Null;"
        "    Write-Output 'burnttoast'"
        "  } else { throw 'no burnttoast' }"
        "}catch{"
        "  try{"
        "    Add-Type -AssemblyName System.Windows.Forms;"
        "    Add-Type -AssemblyName System.Drawing;"
        "    $n=New-Object System.Windows.Forms.NotifyIcon;"
        "    $n.Icon=[System.Drawing.SystemIcons]::Information;"
        "    $n.Visible=$true;"
        "    $n.ShowBalloonTip(20000,$t,$m,[System.Windows.Forms.ToolTipIcon]::Info);"
        "    Start-Sleep -Seconds 8; $n.Dispose();"
        "    Write-Output 'balloon'"
        "  }catch{"
        "    [console]::beep(880,300); [console]::beep(660,300);"
        "    Write-Output 'beep'"
        "  }"
        "}"
    )
    import os
    env = dict(os.environ, DSH_POPUP_TITLE=title, DSH_POPUP_MSG=message)
    for exe in ("powershell.exe", "pwsh.exe"):
        try:
            r = subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                capture_output=True, text=True, timeout=120, env=env,
            )
            out = (r.stdout or "").strip().splitlines()
            tag = out[-1] if out else ""
            if tag:
                label = {"burnttoast": "桌面通知(BurntToast)",
                         "balloon": "气泡通知(WinForms)",
                         "beep": "提示音(通知不可用)"}.get(tag, tag)
                print(f"  [弹窗] {label}")
                return True
        except Exception:
            continue
    print("  [弹窗] 不可用（不影响控制台提醒）")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--no-popup", action="store_true")
    a = ap.parse_args()

    today = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else date.today()
    console, title, tip = build_message(today)
    print(console)
    if not a.no_popup:
        popup(title, tip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
