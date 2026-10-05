# -*- coding: utf-8 -*-
"""12 周计划 · 唯一数据源。

为什么要单独抽出来：
    提醒（reminder.py）、日历（calendar）、进度（progress.py）三个入口都要显示"今天该干什么"。
    文案散在三处，早晚不一致。所以：**任务文案只在这里定义一次。**

用法:
    python schedule.py            # 打印今天
    python schedule.py --all      # 打印完整 12 周日历
    python schedule.py --week 3   # 打印第 3 周
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
START = date(2026, 10, 6)          # 第 1 周 Day 1（周二）
WEEKDAYS = "一二三四五六日"

WEEKS = [
    ("W01", "Agent 核心机制", "AI商业研究助手 v0.1 能跑 + README + Agent 流程图"),
    ("W02", "LangGraph 工程化", "Research Agent v1.0（含人工审核节点）+ 状态图"),
    ("W03", "RAG 与企业知识库", "知识库 Demo + 20题评测(命中率/拒答率) + 企业名单≥10家"),
    ("W04", "Dify / FastGPT", "私有化部署 + 知识库 + FastAPI 工具接口 + 自研vs Dify对照表"),
    ("W05", "企业入口集成", "一个入口端到端跑通 + 60秒录屏 + 架构图"),
    ("W06", "商业 Demo 打造", "完整 Demo（前端+Agent+知识库+后台）+ 场景说明 + 操作手册"),
    ("W07", "案例包装", "展示页 + 3分钟视频 + PPT + 解决方案文档 v1"),
    ("W08", "寻找真实需求", "≥20家触达 + ≥5次真实对话 + 客户需求数据库"),
    ("W09", "确定第一个方向", "方向决策文档（含放弃理由）+ MVP 定义 + 3周计划"),
    ("W10", "低成本试交付", "1个真实交付 + 使用反馈 + 案例授权 + 1个转介绍"),
    ("W11", "标准化交付流程", "交付SOP六步 + 工时表 + 报价公式"),
    ("W12", "建立长期飞轮", "飞轮图 + 3篇内容 + 案例库索引 + 12周总结"),
]

# 每日任务：{周编号: {第几天: 任务}}
TASKS: dict[str, dict[int, str]] = {
    "W01": {
        1: "环境自检 + 配 API Key + 第一次裸调 LLM（python hello_llm.py）",
        2: "跑 tools.py 验证联网搜索；读工具层，想通\"工具要满足什么条件 LLM 才会用\"",
        3: "读 agent.py 的 while 循环；把 max_steps 改成 2，观察报告质量怎么塌",
        4: "跑通 main.py 生成第一份真实报告，检查日志确认它真的搜了网页",
        5: "换成你公众号的真实选题跑 3 个，记录省了多少时间",
        6: "补 README + 画 Agent 流程图 + git 首次提交",
        7: "填 W01 复盘：新增能力 / 资产 / 离赚钱更近了吗 + 写商业线索",
    },
    "W02": {
        1: "读 graph.py（150行迷你状态图引擎），理解 State/Node/Edge",
        2: "跑 workflow.py 看节点流转，注意\"人工审核\"是正式节点",
        3: "动手加\"打回重写\"分支：审核不通过→带意见回到写报告节点",
        4: "试装真 LangGraph 做对照（装不上就跳过，别为环境卡两天）",
        5: "接上 tools.py，让 v1.0 真的能搜网页",
        6: "画状态图 + 写一节：哪些模块能接进我的公众号系统",
        7: "填 W02 复盘 + git 提交 v1.0",
    },
    "W03": {
        1: "读 data/ 里 4 份模拟资料，再补 2-3 篇你自己行业的资料",
        2: "读 split_markdown()；跑实验A(max_chars 200/400/800) 与实验B(overlap 0/80/200)",
        3: "读 search()，想通两道分数门槛（绝对0.25+相对45%）为什么必须同时存在",
        4: "跑通完整问答：先 --no-llm 看检索，再加 Key 看生成",
        5: "加 Rerank；做实验C：--min-score 0.1/0.25/0.5 画误答率vs拒答率曲线",
        6: "跑 --eval 把题库补到20题；做实验D：上 Embedding 救回\"保修期\"同义词问题",
        7: "填 W03 复盘 + 写潜在企业名单初稿（≥10家）",
    },
    "W04": {
        1: "确认 Docker 能跑；装不上就用 Dify 云端版，别卡环境",
        2: "拉 Dify 社区版起服务，建第一个应用",
        3: "把 W03 企业资料灌进 Dify 知识库，对比自研版差异",
        4: "写 FastAPI 暴露 2 个工具接口（查订单/查库存），让 Dify 能调",
        5: "用 Dify Workflow 搭完整流程：提问→检索→判断调API→组装回答",
        6: "做对照表：自研(RAG) vs Dify（开发时间/效果/可维护性/客户能否自改）",
        7: "填 W04 复盘 —— 记下搭这套实际花了几小时，这是报价底线",
    },
    "W05": {
        1: "选入口（建议企业微信）；跑 kb-api 看 /docs 接口文档",
        2: "读官方文档，把回调/Webhook 跑通（先能 echo）",
        3: "接上 Agent：群里@机器人提问→回答（只写入口适配层，别改 do_rag）",
        4: "加会话上下文 + 超时与错误兜底",
        5: "React 写最小聊天窗，fetch /api/ask",
        6: "全链路压测：网络差/问题离谱/3人并发，记录崩溃点",
        7: "填 W05 复盘 + 录 60 秒 Demo 视频",
    },
    "W06": {
        1: "定场景，写一页《场景说明》：谁的什么痛点，用了省多少（禁写技术名词）",
        2: "后端整合：把 W03-W05 的散件收成一个服务",
        3: "前端主界面：聊天 + 引用来源展示",
        4: "后台管理：上传文档 / 问答记录 / 高频问题 Top10",
        5: "造演示数据（Demo 好不好看，一半靠这一步）",
        6: "全流程走一遍，修丑陋处，写《Demo 操作手册》",
        7: "填 W06 复盘 —— 技术阶段到此结束",
    },
    "W07": {
        1: "写展示页文案：把技术名词全部翻译成业务语言",
        2: "搭展示页（React 或一页 HTML，别过度设计）",
        3: "录 3 分钟 Demo 视频（脚本先写：痛点→演示→效果→报价）",
        4: "做 PPT（12 页以内）",
        5: "写《解决方案文档》（用商业资产里的模板）",
        6: "找 3 个人看，记录他们听不懂的地方——那就是要改的地方",
        7: "填 W07 复盘",
    },
    "W08": {
        1: "建客户线索库，列第一批 20 个目标",
        2: "写 3 版开场话术（熟人/陌生/群里）——先问痛点，不推销",
        3: "触达第 1 批 7 家，记录谁回了、谁问了什么",
        4: "触达第 2 批 7 家 + 跟进回复的人",
        5: "触达第 3 批 6 家，目标约到 2 个 15 分钟对话",
        6: "做对话（必问4句：花多少时间/最烦哪步/值多少钱/愿不愿免费试）",
        7: "填 W08 复盘 + 整理需求数据库  ★本周不许写代码★",
    },
    "W09": {
        1: "把需求库摊开，按\"痛点强度×付费意愿×我能交付\"打分",
        2: "砍到 2 个，写各自的 MVP 是什么",
        3: "拿这 2 个去问最有兴趣的那个人：哪个他更想要",
        4: "定 1 个，写《方向决策文档》含放弃理由",
        5: "为选定方向排 3 周交付计划",
        6: "准备试点报价（可免费，但要说清正常价——这是锚点）",
        7: "填 W09 复盘",
    },
    "W10": {
        1: "签一页《试点确认书》（范围/时间/免费但需反馈+案例授权）",
        2: "需求梳理，写《需求确认单》并让客户确认",
        3: "开发/配置交付物",
        4: "交付 + 培训（录屏，以后能复用）",
        5: "收集反馈：好用在哪、难用在哪、会不会推荐",
        6: "要三样：①文字评价 ②案例授权 ③1个转介绍",
        7: "填 W10 复盘",
    },
    "W11": {
        1: "复盘 W10 全过程，按环节统计实际工时",
        2: "写《需求分析清单》",
        3: "写《资料收集清单》+《Agent 设计模板》",
        4: "写《部署清单》",
        5: "写《培训材料模板》+《验收标准》",
        6: "组装成交付SOP，按环节填工时→算出标准报价公式",
        7: "填 W11 复盘",
    },
    "W12": {
        1: "画飞轮图，标出你现在卡在哪一环",
        2: "内容输出：写 3 篇公众号/小红书（案例+方法论+踩坑）",
        3: "更新展示页/案例库，加上真实客户案例（可匿名）",
        4: "找第二单：从需求库挑 3 个最有戏的重新触达",
        5: "建个人案例库索引：做过什么、解决过什么、证据在哪",
        6: "写 12 周总结 + 定下一个 12 周目标",
        7: "最后复盘 + 盘点手上资产",
    },
}


def week_index(d: date) -> int:
    return max(1, min(12, (d - START).days // 7 + 1))


def week_start(wi: int) -> date:
    return START + timedelta(days=(wi - 1) * 7)


def task(wi: int, day_no: int) -> str:
    code = WEEKS[wi - 1][0]
    return TASKS.get(code, {}).get(day_no, "见任务卡")


def fmt_range(wi: int) -> str:
    s = week_start(wi)
    e = s + timedelta(days=6)
    return f"{s:%m/%d}({'一二三四五六日'[s.weekday()]}) ~ {e:%m/%d}({'一二三四五六日'[e.weekday()]})"


def print_today(d: date | None = None):
    d = d or date.today()
    wi = week_index(d)
    ws = week_start(wi)
    day_no = (d - ws).days + 1
    code, title, deliverable = WEEKS[wi - 1]
    print(f"{d:%Y-%m-%d} 星期{WEEKDAYS[d.weekday()]}  |  第 {wi} 周 {code} · {title}  (第 {day_no}/7 天)")
    print(f"今日任务: {task(wi, day_no)}")
    print(f"本周交付: {deliverable}")


def print_week(wi: int, today: date | None = None):
    today = today or date.today()
    code, title, deliverable = WEEKS[wi - 1]
    print("=" * 74)
    print(f"  第 {wi} 周 {code} · {title}      {fmt_range(wi)}")
    print("=" * 74)
    for i in range(1, 8):
        d = week_start(wi) + timedelta(days=i - 1)
        mark = " <== 今天" if d == today else ""
        print(f"  Day{i}  {d:%m/%d}({WEEKDAYS[d.weekday()]})  {task(wi, i)}{mark}")
    print(f"\n  周末必须交出: {deliverable}")
    print("=" * 74)


def print_all(today: date | None = None, fmt: str = "text"):
    today = today or date.today()
    if fmt == "md":
        print("# 12 周作战日历（2026-10-06 ~ 2026-12-28）\n")
        print("> 由 `schedule.py --all --md` 生成。这是唯一权威日历，每天照着做。\n")
        for wi in range(1, 13):
            code, title, deliverable = WEEKS[wi - 1]
            print(f"\n## 第 {wi} 周 · {code} {title}\n")
            print(f"`{fmt_range(wi)}`\n")
            print("| 日期 | 星期 | 今日任务 |")
            print("|---|---|---|")
            for i in range(1, 8):
                d = week_start(wi) + timedelta(days=i - 1)
                mark = " **← 今天**" if d == today else ""
                print(f"| {d:%m/%d}{mark} | {WEEKDAYS[d.weekday()]} | {task(wi, i)} |")
            print(f"\n**周末必须交出**：{deliverable}\n")
        print("\n---\n")
        print("## 每天固定动作\n")
        print("- [ ] 黄金 60 分钟技术块（只做当天任务）")
        print("- [ ] 30 分钟记录：理解了什么 / 解决了什么 / 商业价值 / 客户场景")
        print("- [ ] 5 分钟：写下明天第一件事\n")
        print("## 每周日 21:00 必答\n")
        print("1. 本周新增能力？ 2. 产生什么资产？ 3. 距离赚钱更近了吗？")
        return
    for wi in range(1, 13):
        print_week(wi, today)
        print()


def main():
    ap = argparse.ArgumentParser(description="12周计划日程（唯一数据源）")
    ap.add_argument("--all", action="store_true", help="打印完整日历")
    ap.add_argument("--md", action="store_true", help="--all 时输出 markdown")
    ap.add_argument("--week", type=int, metavar="N", help="打印第 N 周")
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD")
    a = ap.parse_args()

    today = date.fromisoformat(a.date) if a.date else date.today()
    if a.week:
        print_week(a.week, today)
    elif a.all:
        print_all(today, "md" if a.md else "text")
    else:
        print_today(today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
