# -*- coding: utf-8 -*-
"""迷你 StateGraph —— 150 行看懂 LangGraph 的核心。

LangGraph 的三个词，在这份代码里的对应位置：
    State   -> 就是那个 dict（research_state）
    Node    -> add_node(name, fn)，fn(state) -> dict(要更新的字段)
    Edge    -> add_edge(a, b) 固定边 / add_conditional_edge(a, router) 条件边

为什么工程上要用"图"而不是 W01 的 while 循环？
    1) 流程显式：任何人打开图就知道有几步、每步干什么
    2) 能插""人：中断 + 恢复（interrupt / resume）在循环里很难写干净
    3) 可持久化：每个节点的 state 可以存盘，崩了能从中间恢复

用法:
    from graph import StateGraph, END
    g = StateGraph()
    g.add_node("a", fn_a)
    g.add_node("b", fn_b)
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_conditional_edge("b", lambda s: "a" if s["need_more"] else END)
    app = g.compile()
    final_state = app.invoke({"x": 0})
"""
from __future__ import annotations

from typing import Any, Callable

END = "__end__"


class GraphError(RuntimeError):
    pass


class StateGraph:
    def __init__(self, max_steps: int = 25):
        self.nodes: dict[str, Callable[[dict], dict | None]] = {}
        self.edges: dict[str, str] = {}
        self.conds: dict[str, Callable[[dict], str]] = {}
        self.entry: str | None = None
        self.max_steps = max_steps

    # ---------------- 构图 API ----------------
    def add_node(self, name: str, fn: Callable[[dict], dict | None]):
        if name == END:
            raise GraphError(f"'{END}' 是保留名")
        self.nodes[name] = fn
        return self

    def set_entry(self, name: str):
        self.entry = name
        return self

    def add_edge(self, src: str, dst: str):
        self.edges[src] = dst
        return self

    def add_conditional_edge(self, src: str, router: Callable[[dict], str]):
        self.conds[src] = router
        return self

    def compile(self) -> "CompiledGraph":
        if self.entry is None:
            raise GraphError("没有设置入口节点 set_entry()")
        for src, dst in self.edges.items():
            for n in (src, dst):
                if n != END and n not in self.nodes:
                    raise GraphError(f"边引用了不存在的节点: {n}")
        for src in self.conds:
            if src not in self.nodes:
                raise GraphError(f"条件边引用了不存在的节点: {src}")
        return CompiledGraph(self)


class CompiledGraph:
    def __init__(self, g: StateGraph):
        self.g = g

    def next_node(self, current: str, state: dict) -> str:
        if current in self.g.conds:              # 条件边优先
            nxt = self.g.conds[current](state)
            if nxt != END and nxt not in self.g.nodes:
                raise GraphError(f"router 返回了不存在的节点: {nxt}")
            return nxt
        return self.g.edges.get(current, END)

    def invoke(self, state: dict, verbose: bool = True, start: str | None = None) -> dict:
        """跑到底。节点函数返回的 dict 会被合并进 state（这就是 State 的更新语义）。"""
        cur = start or self.g.entry
        for step in range(1, self.g.max_steps + 1):
            if cur == END:
                break
            fn = self.g.nodes[cur]
            if verbose:
                print(f"\n[节点 {step:>2}] {cur}")
            update = fn(state)
            if update:
                if not isinstance(update, dict):
                    raise GraphError(f"节点 {cur} 必须返回 dict 或 None")
                state.update(update)
            cur = self.next_node(cur, state)
        else:
            raise GraphError(f"超过 max_steps={self.g.max_steps}，疑似死循环")
        return state

    def stream(self, state: dict):
        """逐步产出 (节点名, state)，方便做进度条/前端流式展示。"""
        cur = self.g.entry
        for _ in range(self.g.max_steps):
            if cur == END:
                return
            update = self.g.nodes[cur](state)
            if update:
                state.update(update)
            yield cur, state
            cur = self.next_node(cur, state)


def draw_mermaid(g: StateGraph, cond_labels: dict[str, dict[str, str]] | None = None) -> str:
    """把图渲染成 mermaid —— W02 的文档交付物直接用它。

    cond_labels 用来给条件边写上人话标签，例如:
        {"review": {"write": "打回重写", "publish": "通过", "abort": "终止"}}
    """
    cond_labels = cond_labels or {}
    lines = ["```mermaid", "flowchart TD"]
    for name in g.nodes:
        lines.append(f'    {name}["{name}"]')
    for src, dst in g.edges.items():
        if dst == END:
            lines.append(f"    {src} --> DONE([结束])")
        else:
            lines.append(f"    {src} --> {dst}")
    for src in g.conds:
        labels = cond_labels.get(src, {})
        lines.append(f"    {src} {{条件边 router}}")
        for dst, label in labels.items():
            arrow = "DONE([结束])" if dst == END else dst
            lines.append(f"    {src} -->|{label}| {arrow}")
        if not labels:
            lines.append(f"    {src} -.-> 由 router 函数决定")
    lines.append("```")
    return "\n".join(lines)
