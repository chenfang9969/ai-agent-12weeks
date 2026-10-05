# -*- coding: utf-8 -*-
"""Agent 的"手和脚" —— 工具层。

核心认知（Day 2 必须想通）：
    LLM 不能执行任何代码。它只能输出一段 JSON: {"tool": "...", "input": {...}}
    真正干活的是下面这些 Python 函数。
    所以"Agent 能搜索网页"这句话的准确版本是：
        LLM 决定要搜什么  +  我的代码去搜  +  结果喂回 LLM

单独测试:  python tools.py
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _strip_tags(fragment: str, limit: int) -> str:
    fragment = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    fragment = re.sub(r"\s+", " ", fragment).strip()
    return fragment[:limit]


# --------------------------------------------------------------------------
# 工具 1：联网搜索
# --------------------------------------------------------------------------
def web_search(query: str, max_results: int = 5) -> dict:
    """搜索网页，返回 [{title, url, snippet}]。

    注意：DuckDuckGo 的 html 端点偶尔会限流/改版。
    真跑不通时的备选（按性价比排序）：
      1) 换必应 https://www.bing.com/search?q=...
      2) 用 Tavily / Serper / Bocha 的搜索 API（有免费额度，最稳）
      3) 必应 Web Search API（要 key）
    """
    max_results = max(1, min(int(max_results or 5), 10))
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        page = _get(url, timeout=20)
    except Exception as e:
        return {"ok": False, "error": f"搜索请求失败: {type(e).__name__}: {e}", "results": []}

    links = re.findall(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        page,
        flags=re.S,
    )
    snippets = re.findall(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', page, flags=re.S
    )

    results = []
    for i, (href, title) in enumerate(links[:max_results]):
        if "uddg=" in href:
            href = urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
        results.append(
            {
                "title": _strip_tags(title, 160),
                "url": href,
                "snippet": _strip_tags(snippets[i], 500) if i < len(snippets) else "",
            }
        )

    if not results:
        return {"ok": False, "error": "没解析到结果（可能被限流或页面改版）", "results": []}
    return {"ok": True, "results": results}


# --------------------------------------------------------------------------
# 工具 2：抓取单个网页正文
# --------------------------------------------------------------------------
def web_fetch(url: str, max_chars: int = 4000) -> dict:
    """抓取网页并提取纯文本。max_chars 是成本闸门：token 就是钱。"""
    if not url or not url.startswith("http"):
        return {"ok": False, "error": "url 必须以 http 开头", "text": ""}
    max_chars = max(500, min(int(max_chars or 4000), 20000))
    try:
        page = _get(url, timeout=20)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "text": ""}

    body = page
    m = re.search(r"(?is)<(article|main)[^>]*>(.*?)</\1>", page)
    if m:
        body = m.group(2)
    text = _strip_tags(body, max_chars)
    if len(text) < 120:
        return {"ok": False, "error": "正文过短（可能是 JS 动态渲染页）", "text": text}
    return {"ok": True, "text": text, "url": url, "note": f"已截断至 {max_chars} 字符"}


# --------------------------------------------------------------------------
# 工具 3：把结果落盘（Agent 的"笔记本"）
# --------------------------------------------------------------------------
def write_note(title: str, content: str, out_dir: str | None = None) -> dict:
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "-", str(title or "note"))[:60]
    path = os.path.join(out_dir, f"{safe}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(content))
    return {"ok": True, "path": path, "chars": len(str(content))}


# --------------------------------------------------------------------------
# 给 LLM 看的"说明书" —— 工具描述的质量直接决定 Agent 的成败
# --------------------------------------------------------------------------
TOOL_SPECS = [
    {
        "name": "web_search",
        "description": "联网搜索，返回标题/链接/摘要列表。用于获取最新公开信息。",
        "parameters": {
            "query": "搜索关键词，尽量具体，例如 '字节跳动 AI 战略 2025 豆包 投入'",
            "max_results": "返回条数，1-10，默认 5",
        },
    },
    {
        "name": "web_fetch",
        "description": "抓取指定网址的正文纯文本。在 web_search 找到高价值链接后使用。",
        "parameters": {"url": "以 http 开头的完整网址", "max_chars": "最多返回多少字符，默认 4000"},
    },
    {
        "name": "write_note",
        "description": "把阶段性结论写到本地 markdown 文件，防止长任务上下文丢失。",
        "parameters": {"title": "文件名，简短", "content": "markdown 正文"},
    },
]

REGISTRY = {"web_search": web_search, "web_fetch": web_fetch, "write_note": write_note}


def execute(name: str, input_: dict) -> dict:
    """Agent Loop 里的 Action -> Tool 这一步。"""
    fn = REGISTRY.get(name)
    if fn is None:
        return {"ok": False, "error": f"未知工具 {name}，可用: {list(REGISTRY)}"}
    if not isinstance(input_, dict):
        input_ = {"value": input_}
    try:
        return fn(**input_)
    except TypeError as e:
        return {"ok": False, "error": f"参数不匹配: {e}；期望 {TOOL_SPECS[[t['name'] for t in TOOL_SPECS].index(name)]['parameters']}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def as_prompt() -> str:
    """把工具体系渲染成注入 system prompt 的说明书。"""
    lines = ["你可以调用以下工具（每次只能调用一个）：", ""]
    for t in TOOL_SPECS:
        lines.append(f"### {t['name']}")
        lines.append(t["description"])
        for k, v in t["parameters"].items():
            lines.append(f"  - {k}: {v}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 56)
    print("工具自测：web_search")
    print("=" * 56)
    r = web_search("字节跳动 AI 战略 豆包 投入", max_results=3)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:1500])

    print("\n" + "=" * 56)
    print("工具自测：write_note")
    print("=" * 56)
    print(write_note("_selftest", f"工具层自测通过 {time.strftime('%Y-%m-%d %H:%M:%S')}"))
    print("\nDay 2 任务：给 REGISTRY 加一个你自己的工具（例如查你的公众号素材库）。")
