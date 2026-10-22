# -*- coding: utf-8 -*-
r"""【参考实现 · 对照用】

这不是让你抄的东西，是让你**对照着看差异**的东西。
你的文件是 translate_graph.py，这个是 translate_graph_参考.py，两个并存。

用法：
    python translate_graph_参考.py "测试" --mock --auto
    python translate_graph_参考.py "测试" --mock      # 手动 y/n 测打回

每个函数下面都标了「为什么这么写」，那些注释才是重点。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from graph import END, StateGraph, draw_mermaid  # noqa: E402

MAX_ROUND = 3
OUT_DIR = HERE / "output"


# ==========================================================================
# TODO 1 · 翻译节点
# ==========================================================================
def node_translate(state: dict) -> dict:
    # ── 为什么用 state.get("round", 0) 而不是 state["round"]？ ──
    # 因为 dict[key] 在键不存在时会直接 KeyError 崩掉；
    # .get(key, 默认值) 在键不存在时返回默认值，更安全。
    # 这里的 round 在 new_state() 里已经给了 0，所以两种写法都能跑，
    # 但 .get() 是习惯——以后别人（或别的代码）传进来的 state 未必有 round。
    n = state.get("round", 0) + 1

    # ── 为什么先取 feedback 再判断？ ──
    # 因为下面要用它两次：判断"是不是重译"，以及拼进假译文里给人看到。
    feedback = state.get("review_feedback", "")

    if state.get("mock"):
        # mock 模式：不调模型，造个假译文。
        # 关键在于假译文里要能看出"第几稿"和"有没有采纳意见"，
        # 这样你跑测试时一眼就知道流程对不对。
        text = f"[mock 第{n}稿] 译为英文：{state.get('source_text', '')[:30]}"
        if feedback:
            text += f"（已采纳意见：{feedback}）"
    else:
        # 真版本：调 LLM。这里故意留成简单的形式，
        # 你以后想接真翻译，把这一段换成 llm.chat() 就行。
        text = f"[真模式未接入] 第{n}稿，原文：{state.get('source_text', '')}"

    # ── 为什么返回的是一个"只含要改的字段"的 dict？ ──
    # 因为 graph.py 里的 invoke 是这样处理的：
    #     update = fn(state)
    #     if update: state.update(update)
    # 也就是说：你返回什么，引擎就把什么合并进 state。
    # 你不需要返回完整的 state，只返回"这次改动的字段"就够了。
    # 这是状态图最核心的约定，也是你之前容易搞不清的地方。
    return {
        "translation": text,
        "round": n,
        # log 要"在原来的基础上追加"，所以不能直接写 [f"..."]，那样会覆盖掉前面的记录。
        "log": state.get("log", []) + [f"translate: 第{n}稿" + ("（重译）" if feedback else "")],
    }


# ==========================================================================
# TODO 2 · 人工审核节点
# ==========================================================================
def node_review(state: dict) -> dict:
    n = state.get("round", 0)
    text = state.get("translation", "")

    print("\n" + "-" * 60)
    print(f"【人工审核】第 {n} 稿，共 {len(text)} 字")
    print("-" * 60)
    # 只打印前 500 字：长了刷屏，而且审核的人也不需要看全文才能判断
    print(text[:500])
    if len(text) > 500:
        print("...(已截断)")
    print("-" * 60)

    # ── --auto 的处理要放在最前面 ──
    # 因为它在测试和脚本化运行时不能卡在 input() 上等输入，
    # 所以先判断、先返回，才不会走到后面的 input()。
    if state.get("auto"):
        print("[auto] 自动通过")
        return {
            "approved": True,
            "log": state.get("log", []) + [f"review: 第{n}稿 自动通过"],
        }

    # ── while True 的用处 ──
    # 让用户乱敲的时候重新问，而不是程序直接崩掉或记一个错误的值。
    while True:
        ans = input("通过吗？[y=通过 / n=打回]: ").strip().lower()
        if ans in ("y", "yes", ""):
            return {
                "approved": True,
                "log": state.get("log", []) + [f"review: 第{n}稿 人工通过"],
            }
        if ans in ("n", "no"):
            fb = input("请写下修改意见（会喂给下一轮翻译）: ").strip()
            # ── 这里为什么要有 or "重写"？ ──
            # 因为用户可能直接回车，feedback 变成空字符串。
            # 空字符串在 node_translate 里会被当成"没有意见"，
            # 那就等于白打回了一次。所以给个兜底文案。
            return {
                "approved": False,
                "review_feedback": fb or "重写，提高准确性",
                "log": state.get("log", []) + [f"review: 第{n}稿 打回 - {fb[:20]}"],
            }
        print("请输入 y 或 n")


# ==========================================================================
# TODO 3 · 定稿节点
# ==========================================================================
def node_publish(state: dict) -> dict:
    OUT_DIR.mkdir(exist_ok=True)
    n = state.get("round", 0)
    approved = state.get("approved", False)
    # 文件名里带时间，避免连续跑两次互相覆盖
    path = OUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-翻译-v{n}.md"

    lines = []
    # ── 这段就是你在推演表第 10 步定下的决策 ──
    # 没通过审核也要输出（否则前面几轮的工作全白费），
    # 但必须**明确标记**，不能让拿到文件的人以为这是终稿。
    # 这跟 W01 "查不到就写未能获取" 是同一个原则：
    #   宁可不完整，不可不诚实。
    if approved:
        lines.append(f"<!-- 审核状态：已通过 | 第 {n} 稿 -->\n")
    else:
        lines.append("<!-- 审核状态：★未通过审核（达到重译上限，强制输出） -->")
        lines.append(f"<!-- 最后一条审核意见：{state.get('review_feedback', '')} -->")
        lines.append(f"<!-- 第 {n} 稿 -->\n")
        lines.append("> ⚠️ **注意：本译文未通过人工审核，请勿直接使用。**\n")

    lines.append(state.get("translation", ""))
    path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "output_path": str(path),
        "log": state.get("log", []) + [f"publish: {path.name}（{'已通过' if approved else '未通过审核'}）"],
    }


# ==========================================================================
# TODO 4 · 条件边
# ==========================================================================
def route_review(state: dict) -> str:
    # ── 为什么 approved 要先判？ ──
    # 因为"通过"是最强的终止理由：
    # 哪怕这是第 3 稿（上限），只要人通过了，就该输出，而不是去判上限。
    # 顺序反了的话，第 3 稿通过也会被当成"到上限了"处理，
    # 虽然结果一样（都去 publish），但语义就乱了——将来加了别的分支就会出 bug。
    if state.get("approved"):
        return "publish"

    # ── 上限兜底 ──
    # 防止无限循环：人可能一直打回，系统不能陪他转到天荒地老。
    # 注意用 >= 而不是 ==：万一 round 因为某种原因跳过了 3，>= 还能兜住。
    if state.get("round", 0) >= MAX_ROUND:
        return "publish"

    # 剩下的情况：没通过，且还没到上限 -> 回去重译
    return "translate"


# ==========================================================================
# 以下是建图和命令行，和你的文件一样，不用对照
# ==========================================================================
def new_state(topic: str, mock: bool, auto: bool) -> dict:
    return {
        "source_text": topic,
        "translation": "",
        "approved": False,
        "round": 0,
        "review_feedback": "",
        "mock": mock,
        "auto": auto,
        "log": [],
    }


def build() -> StateGraph:
    g = StateGraph(max_steps=20)
    g.add_node("translate", node_translate)
    g.add_node("review", node_review)
    g.add_node("publish", node_publish)
    g.set_entry("translate")
    g.add_edge("translate", "review")
    g.add_conditional_edge("review", route_review)
    g.add_edge("publish", END)
    return g


def main() -> int:
    ap = argparse.ArgumentParser(description="文章翻译审校（参考实现）")
    ap.add_argument("text", nargs="?", default="这是一篇关于人工智能的中文文章。")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--draw", action="store_true")
    a = ap.parse_args()

    g = build()
    if a.draw:
        print(draw_mermaid(g, {"review": {"publish": "通过/超过上限", "translate": "打回重译"}}))
        return 0

    final = g.compile().invoke(new_state(a.text, a.mock, a.auto), verbose=True)
    print("\n" + "=" * 64)
    print("执行轨迹：")
    for line in final.get("log", []):
        print("   -", line)
    print(f"\n总轮数: {final.get('round')}   通过审核: {final.get('approved')}")
    print(f"落盘: {final.get('output_path')}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
