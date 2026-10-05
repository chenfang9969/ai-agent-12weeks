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


def parse_action(text: str) -> dict:
    """把 LLM 输出解析成结构化动作。容错：去代码块、截最外层花括号。"""
    if not text:
        return {"thought": "空输出", "action": None, "final": None}
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    obj = None
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                obj = None
    if not isinstance(obj, dict):
        # 模型没按格式来：把原文当最终答案，避免整轮白跑
        return {"thought": "(未按 JSON 格式输出)", "action": None, "final": t}
    return {
        "thought": obj.get("thought", ""),
        "action": obj.get("action"),
        "final": obj.get("final"),
    }


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
        for step in range(1, self.max_steps + 1):
            self._say(f"\n[Step {step}] 思考中 ...")
            raw = self._think()
            parsed = parse_action(raw)

            if parsed["thought"]:
                self._say(f"  Thought : {parsed['thought'][:200]}")

            # 终止条件：模型认为资料够了
            if parsed["final"] and not parsed["action"]:
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
