# -*- coding: utf-8 -*-
"""Research Agent v1.0 —— 用"显式状态图"重写 W01 的 while 循环。

    plan(生成研究计划)
      |
    gather(收集资料)  <──────────────┐
      |                              │
    write(写报告)                    │
      |                              │
    review(人工审核) ──打回(with feedback)┘
      |  通过
    publish(输出)

对比 W01 的进步：
    W01: while 循环，模型自己决定一切，"人"插不进去
    W02: 流程是显式的，"人工审核"是一个正式节点 —— 企业客户最在意这个

用法:
    python workflow.py "分析某公司AI战略"
    python workflow.py "某主题" --auto          # 无人值守，自动通过审核
    python workflow.py "某主题" --mock          # 不调 LLM，只验证图结构
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ai-research-agent"))

from graph import END, StateGraph, draw_mermaid  # noqa: E402


# ==========================================================================
# 节点定义：每个节点都是 (state) -> dict 的纯函数
# ==========================================================================
def node_plan(state: dict) -> dict:
    """生成研究计划。"""
    topic = state["topic"]
    if state.get("mock"):
        return {"plan": [f"{topic} 的现状", f"{topic} 的关键动作", f"{topic} 的风险"],
                "log": state.get("log", []) + ["plan(mock)"]}
    from llm import chat, pick_provider
    p = pick_provider()
    r = chat(p, [
        {"role": "system", "content": "你是研究规划专家。输出 3-5 条研究子问题，每行一条，不要编号以外的东西。"},
        {"role": "user", "content": f"研究主题：{topic}"},
    ])
    plan = [l.strip(" -•\t") for l in r.text.splitlines() if l.strip()][:5]
    return {"plan": plan, "log": state.get("log", []) + [f"plan: {len(plan)} 条子问题"]}


def node_gather(state: dict) -> dict:
    """收集资料（调 W01 的工具层）。"""
    if state.get("mock"):
        return {"notes": state.get("notes", []) + ["(mock 资料)"],
                "log": state.get("log", []) + ["gather(mock)"]}
    import tools as T
    notes = list(state.get("notes", []))
    for q in state.get("plan", [])[:3]:            # 控制成本：最多搜 3 条
        r = T.web_search(q, max_results=3)
        if r.get("ok"):
            for it in r["results"]:
                notes.append(f"[{it['title']}] {it['snippet']}  <{it['url']}>")
    return {"notes": notes, "log": state.get("log", []) + [f"gather: {len(notes)} 条资料"]}


def node_write(state: dict) -> dict:
    """写报告。如果带着审核意见，就是"修改稿"。"""
    fb = state.get("feedback")
    if state.get("mock"):
        return {"draft": f"# {state['topic']} · 分析（mock 第{state.get('round',1)}稿）\n\n"
                         f"审核意见：{fb or '无'}",
                "round": state.get("round", 1) + 1,
                "log": state.get("log", []) + ["write(mock)"]}
    from llm import chat, pick_provider
    p = pick_provider()
    notes = "\n".join(state.get("notes", []))[:8000]
    user = f"主题：{state['topic']}\n研究计划：{state.get('plan')}\n资料：\n{notes}\n"
    if fb:
        user += f"\n【上一稿的审核意见，必须针对性修改】{fb}\n"
    r = chat(p, [
        {"role": "system", "content":
            "你是商业分析师。基于给定资料写中文分析报告，markdown 格式。"
            "结构：结论先行 / 关键动作与时间线 / 商业化落地 / 风险 / 参考来源。"
            "只使用资料里的信息，不许编造。资料不足就写'未能获取'。"},
        {"role": "user", "content": user},
    ], temperature=0.3)
    return {"draft": r.text, "round": state.get("round", 1) + 1,
            "log": state.get("log", []) + [f"write: 第{state.get('round', 1)}稿 {len(r.text)}字"]}


def node_review(state: dict) -> dict:
    """★ 人工审核节点 —— 这是企业客户愿意付钱的地方。"""
    if state.get("auto"):
        print("\n[人工审核] --auto 模式，自动通过")
        return {"approved": True, "feedback": None,
                "log": state.get("log", []) + ["review: 自动通过"]}

    print("\n" + "=" * 64)
    print(f"【人工审核】第 {state.get('round', 1)} 稿，共 {len(state.get('draft', ''))} 字")
    print("=" * 64)
    print(state.get("draft", "")[:1200])
    if len(state.get("draft", "")) > 1200:
        print("... (已省略，完整稿见 output/)")
    while True:
        ans = input("\n审核决定 [y=通过 / n=打回重写 / q=终止]: ").strip().lower()
        if ans in ("y", "yes", ""):
            return {"approved": True, "feedback": None,
                    "log": state.get("log", []) + ["review: 人工通过"]}
        if ans in ("n", "no"):
            fb = input("请写下修改意见（会喂回给模型）: ").strip()
            return {"approved": False, "feedback": fb or "重写，提高信息密度与具体性",
                    "log": state.get("log", []) + [f"review: 打回 - {fb[:40]}"]}
        if ans in ("q", "quit"):
            return {"approved": False, "aborted": True,
                    "log": state.get("log", []) + ["review: 人工终止"]}
        print("请输入 y / n / q")


def node_publish(state: dict) -> dict:
    """定稿落盘。"""
    out = HERE / "output"
    out.mkdir(exist_ok=True)
    path = out / f"{datetime.now():%Y%m%d-%H%M%S}-v1.0.md"
    head = (f"<!-- Research Agent v1.0 | 审核轮次={state.get('round', 1)} "
            f"| 审核意见={state.get('feedback') or '一次通过'} -->\n\n")
    path.write_text(head + state.get("draft", ""), encoding="utf-8")
    print(f"\n[定稿] {path}")
    return {"final_path": str(path),
            "log": state.get("log", []) + [f"publish: {path.name}"]}


def node_abort(state: dict) -> dict:
    print("\n[终止] 人工审核未通过且选择终止，流程停止。")
    return {"log": state.get("log", []) + ["abort"]}


# ==========================================================================
# 路由函数：这就是"条件边" —— 一个根据 state 返回下一个节点名的函数
# ==========================================================================
def route_review(state: dict) -> str:
    if state.get("aborted"):
        return "abort"
    if state.get("approved"):
        return "publish"
    if state.get("round", 1) >= 4:          # 防止无限打回，烧钱
        print("\n[!] 已改 4 稿，强制定稿（真实项目必须设这个上限）")
        return "publish"
    return "write"                           # 打回重写


def build():
    g = StateGraph(max_steps=30)
    g.add_node("plan", node_plan)
    g.add_node("gather", node_gather)
    g.add_node("write", node_write)
    g.add_node("review", node_review)
    g.add_node("publish", node_publish)
    g.add_node("abort", node_abort)

    g.set_entry("plan")
    g.add_edge("plan", "gather")
    g.add_edge("gather", "write")
    g.add_edge("write", "review")
    g.add_conditional_edge("review", route_review)   # ★ 条件边
    g.add_edge("publish", END)
    g.add_edge("abort", END)
    return g


def main():
    ap = argparse.ArgumentParser(description="Research Agent v1.0（状态图版）")
    ap.add_argument("topic", nargs="?", default="分析某公司AI战略")
    ap.add_argument("--auto", action="store_true", help="自动通过人工审核")
    ap.add_argument("--mock", action="store_true", help="不调 LLM，只验证图能否跑通")
    ap.add_argument("--draw", action="store_true", help="只打印 mermaid 状态图")
    args = ap.parse_args()

    g = build()
    if args.draw:
        print(draw_mermaid(g, {"review": {"publish": "通过", "write": "打回重写", "abort": "终止"}}))
        return 0

    app = g.compile()
    state = {
        "topic": args.topic, "plan": [], "notes": [], "draft": "",
        "round": 1, "approved": False, "feedback": None, "aborted": False,
        "auto": args.auto, "mock": args.mock, "log": [],
    }
    try:
        final = app.invoke(state)
    except Exception as e:
        print(f"\n[失败] {type(e).__name__}: {e}")
        return 1

    print("\n" + "=" * 64)
    print("执行轨迹：")
    for line in final.get("log", []):
        print("   -", line)
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
