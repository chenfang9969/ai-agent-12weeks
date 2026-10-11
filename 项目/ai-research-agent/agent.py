# -*- coding: utf-8 -*-
"""Agent Loop 本体 —— 整个 Agent 就是下面那个 while 循环。

    Goal -> Reasoning -> Action -> Tool -> Observation -> 继续决策

Day 3 的把戏：把 max_steps 改成 2 跑一次，看报告质量怎么塌。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools as T  # noqa: E402
from llm import LLMError, chat, estimate_cost, pick_provider  # noqa: E402

SYSTEM = """你是一个"AI 商业研究助手"。你的任务是通过调用工具收集真实资料，最终产出一份中文商业分析。

{TOOLS}

## 输出规则（严格遵守）
每一轮你只能输出一个 JSON 对象，不要输出任何多余文字、不要用 markdown 代码块包裹。

需要调用工具时：
{{"thought": "我为什么需要这一步", "action": {{"tool": "工具名", "input": {{"参数名": "参数值"}}}}}}

资料已足够、可以给最终答案时：
{{"thought": "资料足够了", "final": "最终答案全文"}}

## 研究纪律
1. 至少先做 2 次 web_search（不同角度），再决定是否 web_fetch。
2. 只使用观察结果里的信息，绝不允许编造数字、日期、事件。
3. 资料不足以回答时，明确写"未能获取"，不要猜。
4. 引用具体来源时写出网址。

## 最终报告结构（final 字段里用 markdown）
# {TOPIC} · AI 战略分析
## 1. 结论先行（3 条以内）
## 2. 关键动作与时间线
## 3. 商业化落地
## 4. 风险与不确定性
## 5. 对个人开发者的机会点（重点，要给具体可执行的方向）
## 6. 参考来源
"""


def _iter_json_objects(text: str):
    """从左到右扫出所有"括号配对完整"的 JSON 对象（跳过字符串内的括号）。

    为什么要自己写而不是用正则：
        正则 r"\\{.*\\}" 是贪婪的，会把模型吐出的多个 JSON 连同中间的文字
        一起吞进去，json.loads 必然失败。
    实测踩到的坑（2026-10-10）：模型一次输出
        {"thought":..., "action":{...}}
        <system>【工具观察】{"ok":true, ...}
    贪婪正则把两段连成一坨 -> 解析失败 -> 整轮被当成"最终答案" ->
    工具一次都没调用，循环提前结束。
    """
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    yield text[start:i + 1]
                    start = -1


def parse_action(text: str) -> dict:
    """把 LLM 输出解析成结构化动作。

    顺序：
      1. 去掉 markdown 代码块
      2. 整段直接 json.loads（最理想）
      3. 否则按括号配对找出所有 JSON 对象，取**第一个**含
         thought/action/final 字段的
      4. 都不行才退化：把原文当最终答案（避免整轮白跑）
    """
    if not text:
        return {"thought": "空输出", "action": None, "final": None}
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()

    candidates: list[dict] = []
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            candidates.append(obj)
    except json.JSONDecodeError:
        pass

    if not candidates:
        for frag in _iter_json_objects(t):
            try:
                o = json.loads(frag)
            except json.JSONDecodeError:
                continue
            if isinstance(o, dict) and ({"thought", "action", "final"} & set(o)):
                candidates.append(o)

    for obj in candidates:
        # 优先取"有 action"的（说明它要干活），其次才接受 final
        if obj.get("action"):
            return {"thought": obj.get("thought", ""), "action": obj["action"],
                    "final": obj.get("final")}
    for obj in candidates:
        if obj.get("final"):
            return {"thought": obj.get("thought", ""), "action": None, "final": obj["final"]}

    # 模型没按格式来：把原文当最终答案，避免整轮白跑
    return {"thought": "(未按 JSON 格式输出)", "action": None, "final": t}


class ResearchAgent:
    def __init__(self, max_steps: int = 10, temperature: float = 0.3, verbose: bool = True):
        self.provider = pick_provider()
        self.max_steps = max_steps
        self.temperature = temperature
        self.verbose = verbose
        self.log: list[dict] = []
        self.messages: list[dict] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _say(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _think(self) -> str:
        r = chat(self.provider, self.messages, temperature=self.temperature)
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.completion_tokens
        self.log.append({"role": "llm", "prompt_tokens": r.prompt_tokens,
                         "completion_tokens": r.completion_tokens})
        return r.text

    def _think_json(self, max_repair: int = 2) -> tuple[str, dict]:
        """要一轮 JSON；如果模型没按格式来，就让它重说一遍。

        为什么需要"重说"这一步（2026-10-10 实测）：
            模型偶尔会一次性吐出一大段东西：先是 JSON，接着又自己模仿
            <system>【工具观察】... 的格式编一段假的工具返回。
            解析失败后旧代码直接把整段当"最终答案"，导致**工具一次都没调用**
            就结束了 —— 输出的是凭记忆编的报告，而且里面还有假的时间。

        修法：解析失败时不放弃，而是告诉它"格式不对，只回一个 JSON"，
        最多重试 max_repair 次。这是真实 Agent 必须有的鲁棒性。
        """
        raw = self._think()
        for attempt in range(max_repair + 1):
            parsed = parse_action(raw)
            ok = bool(parsed["action"]) or bool(parsed["final"])
            if ok:
                return raw, parsed
            if attempt >= max_repair:
                break
            self._say(f"  [!] 输出格式不符（第 {attempt + 1} 次），要求它重说一遍 ...")
            self.messages.append({"role": "assistant", "content": raw[:2000]})
            self.messages.append({
                "role": "user",
                "content": ("你上一条回复格式不对，无法解析。请**只**输出一个 JSON 对象，"
                            "不要输出任何解释、不要自己编造工具返回结果"
                            "（工具结果由系统提供，你不需要也不会写 <system> 标签）。\n"
                            '要调用工具: {"thought": "...", "action": {"tool": "工具名", "input": {...}}}\n'
                            '要收尾: {"thought": "...", "final": "报告全文"}'),
            })
            raw = self._think()
        return raw, parse_action(raw)

    def research(self, topic: str) -> str:
        self.messages = [
            {"role": "system",
             "content": SYSTEM.replace("{TOOLS}", T.as_prompt()).replace("{TOPIC}", topic)},
            {"role": "user", "content": f"研究主题：{topic}\n请开始。"},
        ]

        self._say("\n" + "=" * 64)
        self._say(f"研究主题: {topic}   (max_steps={self.max_steps})")
        self._say("=" * 64)

        report = "(未能生成报告)"
        tool_calls = 0          # 真正执行过的工具次数
        MIN_RESEARCH = 2        # 至少调研这么多次，才允许它交报告

        for step in range(1, self.max_steps + 1):
            self._say(f"\n[Step {step}] 思考中 ...")
            raw, parsed = self._think_json()

            if parsed["thought"]:
                self._say(f"  Thought : {parsed['thought'][:200]}")

            # ---- 终止条件：模型认为资料够了 ----
            if parsed["final"] and not parsed["action"]:
                # ★ 硬约束：一次调研都没做就想交报告 -> 驳回。
                #   为什么必须用代码拦，而不是靠提示词求它：
                #   实测(2026-10-08~10-10) 提示词里写了"至少先做 2 次 web_search"，
                #   模型照样 7 次直接凭记忆编报告（输入 tokens 只有 507，
                #   说明它连一次工具观察都没收到）。提示词是请求，代码才是约束。
                if tool_calls < MIN_RESEARCH and step <= self.max_steps - 1:
                    self._say(f"  [!] 驳回：还没调研就交报告（已调研 {tool_calls}/{MIN_RESEARCH} 次）")
                    self.messages.append({"role": "assistant", "content": raw[:1500]})
                    self.messages.append({
                        "role": "user",
                        "content": (f"驳回。你到现在只调研了 {tool_calls} 次，不足以支撑任何结论。\n"
                                    f"**禁止现在输出报告**。你必须先调用工具收集资料"
                                    f"（至少再用 web_search 搜 {MIN_RESEARCH - tool_calls} 次）。\n"
                                    '只输出这个格式: {"thought": "...", "action": {"tool": "web_search", "input": {"query": "..."}}}'),
                    })
                    continue
                self._say("  -> 决策: 输出最终报告")
                report = parsed["final"]
                break

            act = parsed["action"] or {}
            name, input_ = act.get("tool"), act.get("input", {})
            if not name:
                self._say("  -> 无有效动作，收尾")
                report = parsed["final"] or raw
                break

            self._say(f"  Action  : {name}({json.dumps(input_, ensure_ascii=False)})")
            result = T.execute(name, input_)
            tool_calls += 1

            # Observation 压缩：喂回上下文前裁剪，控制 token 成本
            brief = json.dumps(result, ensure_ascii=False)
            if len(brief) > 6000:
                brief = brief[:6000] + "...(已截断)"
            ok = result.get("ok")
            self._say(f"  Observe : {'成功' if ok else '失败'}  {'' if ok else result.get('error', '')}")

            self.log.append({"role": "tool", "tool": name, "input": input_, "ok": ok})
            self.messages.append({"role": "assistant", "content": raw})
            self.messages.append({
                "role": "user",
                "content": f"【工具观察 Observation】{brief}\n\n继续，或给最终答案。",
            })
        else:
            # 循环用尽仍未收敛：强制收口，这是真实 Agent 的常见分支
            self._say("\n[!] 达到 max_steps，强制生成报告 ...")
            self.messages.append({
                "role": "user",
                "content": "步数已用尽。请立刻基于已有观察输出最终报告（JSON 的 final 字段）。",
            })
            report = parse_action(self._think())["final"] or "(未能生成报告)"

        self._dump_log(topic)
        return report

    @property
    def cost(self) -> float:
        return estimate_cost(self.provider, self.prompt_tokens, self.completion_tokens)

    def _dump_log(self, topic: str):
        out = Path(__file__).resolve().parent / "output"
        out.mkdir(exist_ok=True)
        p = out / f"_log-{datetime.now():%Y%m%d-%H%M%S}.json"
        p.write_text(
            json.dumps({
                "topic": topic,
                "model": self.provider.model,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cost_yuan": round(self.cost, 4),
                "steps": self.log,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._say(f"\n[日志] {p}")
