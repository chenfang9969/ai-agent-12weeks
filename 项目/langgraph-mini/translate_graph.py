# -*- coding: utf-8 -*-
r"""文章翻译审校 · 状态图实现（W02 Day 3 练习）

用法:
    python translate_graph.py "这是一篇中文文章" --mock --auto   # 不调模型，自动过审
    python translate_graph.py "这是一篇中文文章" --mock          # 手动按 y/n，测打回重译
    python translate_graph.py "这是一篇中文文章" --auto          # 真调 LLM，自动过审
    python translate_graph.py --draw                              # 只看状态图

你要填的只有 4 个函数（都标了 TODO）。其余部分（建图、命令行、落盘）已经写好了。

设计依据: 1013设计图.docx / 1014推演表.docx
  State: source_text / translation / approved / round / review_feedback
  节点  : translate -> review -> publish
  条件边: approved -> publish ; round>=3 -> publish ; 否则 -> translate
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
sys.path.insert(0, str(HERE.parent / "ai-research-agent"))
from llm import LLMError, chat, pick_provider

MAX_ROUND = 3          # 最多翻译几稿（含第 1 稿）
OUT_DIR = HERE / "output"


# ==========================================================================
# TODO 1：翻译节点
# ==========================================================================
def node_translate(state: dict) -> dict:
    """翻译 / 按审核意见重译。

    要求：
      1. round += 1（入口时 round=0，所以第一次进来变成 1）
      2. 产出 translation
      3. 如果 review_feedback 不为空，说明这是"重译"，要把意见考虑进去
      4. mock 模式下不要调模型，造一个假译文就行，例如 f"[mock 第{n}稿] ..."

    返回示例：{"translation": "......", "round": 2, "log": [...]}
    """
    # TODO: 请在这里实现
    n=state["round"]+1
    source=state["source_text"]
    feedback=state.get("review_feedback", "")
    if state["mock"]:
        translation = f"[mock 第{n}稿] {state['source_text']}"
    else:
        user_msg = f"原文（中文）：\n{state['source_text']}\n"
        if feedback:
            user_msg += f"\n上一轮审核意见：{feedback}\n请据此修改译文。"
        resp = chat(pick_provider(), [
            {"role": "system", "content": "你是专业翻译。把用户给的中文翻成英文，只输出译文本身，不要解释。"},
            {"role": "user", "content": user_msg},
        ], temperature=0.3)
        text = resp.text.strip()
    
    return {
        "translation":text,
        "round":n,
        "log": state.get("log", []) + [f"translate: 第{n}稿" + ("（重译）" if feedback else "")],
        "review_feedback":"",
    }



# ==========================================================================
# TODO 2：人工审核节点
# ==========================================================================
def node_review(state: dict) -> dict:
    """人工审核。

    要求：
      1. 把当前 translation 打印出来给人看（只打印前 500 字就够了）
      2. --auto 模式下直接通过
      3. 否则 input() 收 y/n：
           y -> approved=True
           n -> approved=False，并再 input() 收一条修改意见，写进 review_feedback

    返回示例：{"approved": True} 或 {"approved": False, "review_feedback": "太生硬"}
    """
    # TODO: 请在这里实现
    print(f"[翻译第{state["round"]}稿] {state["translation"][:500]}")
    if state["auto"]:
        state.update(approved=True)
    else:
        approved = input("请按 y/n 审核：")
        if approved == "y":
            state.update(approved=True)
        else:
            state.update(
                approved=False,
                review_feedback=input("请输入修改意见："),
            )
    


# ==========================================================================
# TODO 3：定稿节点
# ==========================================================================
def node_publish(state: dict) -> dict:
    """定稿落盘。

    要求：
      1. 把 translation 写到 output/ 下，文件名带时间
      2. ★ 关键：如果是被强制定稿的（approved=False），
         文件开头必须写明「未通过审核」+ 最后一条审核意见
         —— 这是 1014 推演表第 10 步定下的决策：不骗人

    返回示例：{"output_path": "..."}
    """
    # TODO: 请在这里实现
    OUT_DIR.mkdir(exist_ok=True)
    n = state["round"]
    approved = state["approved"]
    path = OUT_DIR / f"{datetime.now():%Y%m%d%H%M%S}-翻译-v{n}.md"

    head = []
    if approved:
        head.append(f"<!-- 审核状态：已通过 | 第 {n} 稿 -->")
    else:
        head.append("<!-- 审核状态：未通过审核（达上限强制输出） -->")
        head.append(f"<!-- 最后一条意见：{state.get('review_feedback','')} -->")
        head.append(f"> 本译文未通过审核，请勿直接使用。")

    path.write_text("\n".join(head) + "\n\n" + state["translation"], encoding="utf-8")

    return {
        "output_path": str(path),
        "log": state.get("log", []) + [f"publish: {path.name}（{'已通过' if approved else '未通过'}）"],
    }


# ==========================================================================
# TODO 4：条件边（router）
# ==========================================================================
def route_review(state: dict) -> str:
    """审核之后往哪走。返回的是**节点名字符串**。

    判断顺序（推演表里你已经填对了）：
      1. approved 为真              -> "publish"
      2. round >= MAX_ROUND         -> "publish"   （强制收口）
      3. 其余                       -> "translate" （打回重译）
    """
    # TODO: 请在这里实现
    if state["approved"]:
        return "publish"
    elif state["round"] >= MAX_ROUND:
        return "publish"
    else:
        return "translate"
    raise NotImplementedError("TODO 4: route_review 还没实现")


# ==========================================================================
# 以下是已经写好的部分，不用改
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
    g.add_conditional_edge("review", route_review)   # 分岔在审核之后
    g.add_edge("publish", END)
    return g


def main() -> int:
    ap = argparse.ArgumentParser(description="文章翻译审校（状态图版）")
    ap.add_argument("text", nargs="?", default="这是一篇关于人工智能的中文文章。", help="要翻译的中文")
    ap.add_argument("--mock", action="store_true", help="不调模型，只验证图能不能跑")
    ap.add_argument("--auto", action="store_true", help="自动通过审核，不打断")
    ap.add_argument("--draw", action="store_true", help="只打印状态图")
    a = ap.parse_args()

    g = build()
    if a.draw:
        print(draw_mermaid(g, {"review": {"publish": "通过/超过上限", "translate": "打回重译"}}))
        return 0

    app = g.compile()
    state = new_state(a.text, a.mock, a.auto)
    try:
        final = app.invoke(state, verbose=True)
    except NotImplementedError as e:
        print(f"\n[还没做完] {e}")
        return 1
    except Exception as e:
        print(f"\n[失败] {type(e).__name__}: {e}")
        return 1

    print("\n" + "=" * 64)
    print("执行轨迹：")
    for line in final.get("log", []):
        print("   -", line)
    print(f"\n总轮数: {final.get('round')}   通过审核: {final.get('approved')}")
    print(f"落盘: {final.get('output_path', '(未落盘)')}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
