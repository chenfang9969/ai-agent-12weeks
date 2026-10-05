# -*- coding: utf-8 -*-
"""极简 LLM 调用层 —— 只用标准库，不依赖 openai SDK。

为什么手写而不用 SDK？
  1) 你的环境里 httpx 0.13.3 太旧，在 Python 3.13 上 import 就崩（cgi 模块已移除）
  2) Week 1 的目的是看清底层：LLM 调用本质就是一个 HTTP POST + JSON
  3) 想换任何 OpenAI 兼容模型（DeepSeek/通义/Kimi/智谱/本地 vLLM）只改 base_url

用法:
    from llm import chat, pick_provider
    p = pick_provider()
    r = chat(p, [{"role": "user", "content": "你好"}])
    print(r.text, r.total_tokens)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# 可选：支持从项目根目录的 .env 读取 Key（装了 python-dotenv 才生效，没装也不报错）
# 好处：不用每次开新窗口都敲 $env:XXX_API_KEY="..."
try:
    from pathlib import Path as _Path

    from dotenv import load_dotenv as _load_dotenv

    for _p in (_Path(__file__).resolve().parent / ".env",
               _Path(__file__).resolve().parents[2] / ".env"):
        if _p.exists():
            _load_dotenv(_p, override=False)
except Exception:
    pass

# (环境变量名, base_url, 默认模型, 单价估算 元/百万token 输入, 输出)
PROVIDERS = [
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat", 1.0, 2.0),
    ("DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", 0.8, 2.0),
    ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k", 12.0, 12.0),
    ("ZHIPUAI_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", 0.0, 0.0),
    ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini", 1.1, 4.3),
    # 本地模型：零成本、零注册、数据不出机器。
    # 用法（以 Ollama 为例）:
    #   1) 装 Ollama: https://ollama.com/download
    #   2) ollama pull qwen2.5:7b
    #   3) $env:DSH_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
    #      $env:DSH_LOCAL_MODEL="qwen2.5:7b"
    # 也适用于 LM Studio / vLLM / llama.cpp server（都是 OpenAI 兼容接口）。
    #
    # ⚠️ 本机为 Intel 核显 + 16G 内存，跑本地模型会很慢（每秒几个 token），
    #    不建议作为主力。但代码路径已就绪，换机器或装了 Ollama 即可直接用。
    ("DSH_LOCAL_BASE_URL", "", "", 0.0, 0.0),
]

# 本地供应商的环境变量名不是 API Key，而是 base_url，需要特殊处理
LOCAL_BASE_VAR = "DSH_LOCAL_BASE_URL"
LOCAL_MODEL_VAR = "DSH_LOCAL_MODEL"
LOCAL_DEFAULT_MODEL = "qwen2.5:7b"


@dataclass
class Provider:
    env_var: str
    base_url: str
    model: str
    api_key: str
    price_in: float = 0.0
    price_out: float = 0.0


@dataclass
class Reply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMError(RuntimeError):
    pass


def pick_provider(model: str | None = None) -> Provider:
    """自动挑一个已配置的供应商。云端优先（更快更聪明），本地作为零成本兜底。"""
    # 1) 云端 API
    for var, base, m, pin, pout in PROVIDERS:
        if var == LOCAL_BASE_VAR:
            continue
        key = os.getenv(var)
        if key:
            return Provider(var, base, model or m, key, pin, pout)

    # 2) 本地模型（Ollama / LM Studio / vLLM，OpenAI 兼容接口）
    base = os.getenv(LOCAL_BASE_VAR)
    if base:
        return Provider(LOCAL_BASE_VAR, base, model or os.getenv(LOCAL_MODEL_VAR, LOCAL_DEFAULT_MODEL),
                        "no-key-needed", 0.0, 0.0)

    raise LLMError(
        "没有找到任何可用的模型。三选一：\n\n"
        "  【A】云端 API（推荐，最省事）\n"
        '    $env:DEEPSEEK_API_KEY="sk-xxxx"\n'
        "    申请: https://platform.deepseek.com/api_keys\n\n"
        "  【B】免费额度（零成本起步）\n"
        "    智谱 GLM: glm-4-flash 免费  https://open.bigmodel.cn/\n"
        "    阿里通义: 新用户免费额度    https://bailian.console.aliyun.com/\n\n"
        "  【C】本地模型（零成本、零注册、数据不出机器，但对硬件有要求）\n"
        "    本机是 Intel 核显 + 16G 内存，跑 7B 模型约每秒几个 token，会很慢。\n"
        "    若仍要试: 装 Ollama -> ollama pull qwen2.5:7b -> 然后设置:\n"
        '      $env:DSH_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"\n'
        '      $env:DSH_LOCAL_MODEL="qwen2.5:7b"\n'
        "    也可以把 .env.example 改成 .env 后填入，配一次长期有效。"
    )


def chat(
    provider: Provider,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int | None = None,
    retries: int = 3,
    timeout: int = 120,
) -> Reply:
    """一次补全。带指数退避重试 —— 真实项目必须有的东西。"""
    payload = {"model": provider.model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = provider.base_url.rstrip("/") + "/chat/completions"

    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")[:400]
            last_err = f"HTTP {e.code}: {detail}"
            if e.code in (400, 401, 403, 404):  # 配置错，重试无意义
                raise LLMError(last_err)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            wait = 2 ** (attempt - 1)
            print(f"  [重试 {attempt}/{retries - 1}] {last_err} -> {wait}s 后再试")
            time.sleep(wait)
    else:
        raise LLMError(f"调用失败（已重试 {retries} 次）: {last_err}")

    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise LLMError(f"返回结构异常: {e} | {json.dumps(data, ensure_ascii=False)[:300]}")

    usage = data.get("usage") or {}
    return Reply(
        text=text,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        raw=data,
    )


def estimate_cost(provider: Provider, prompt_tokens: int, completion_tokens: int) -> float:
    """粗略成本（元）。商业方案报价时你会需要这个数。"""
    return prompt_tokens / 1e6 * provider.price_in + completion_tokens / 1e6 * provider.price_out


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = pick_provider()
    print(f"[配置] {p.env_var} | {p.model} | {p.base_url}")
    r = chat(p, [{"role": "user", "content": "只回四个字：连接成功"}])
    print("[回复]", r.text.strip())
    print(f"[用量] 输入 {r.prompt_tokens} / 输出 {r.completion_tokens} / 合计 {r.total_tokens} tokens")
    print(f"[成本] 约 {estimate_cost(p, r.prompt_tokens, r.completion_tokens):.6f} 元")
