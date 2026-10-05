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
_SEARCH_STATE = {"backend": 0, "fail": 0}


def _parse_ddg(html_page: str, max_results: int) -> list[dict]:
    links = re.findall(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html_page, flags=re.S)
    snippets = re.findall(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', html_page, flags=re.S)
    out = []
    for i, (href, title) in enumerate(links[:max_results]):
        if "uddg=" in href:
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                href = urllib.parse.unquote(m.group(1))
        out.append({"title": _strip_tags(title, 160), "url": href,
                    "snippet": _strip_tags(snippets[i], 500) if i < len(snippets) else ""})
    return out


def _parse_ddg_lite(html_page: str, max_results: int) -> list[dict]:
    """DuckDuckGo Lite：页面更简单，限流更宽松。"""
    out = []
    for m in re.finditer(
        r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_page, flags=re.S
    ):
        href, title = m.group(1), _strip_tags(m.group(2), 160)
        if href.startswith("//"):
            href = "https:" + href
        out.append({"title": title, "url": href, "snippet": ""})
        if len(out) >= max_results:
            break
    if not out:  # 新版 lite 结构回退
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html_page, flags=re.S):
            href, title = m.group(1), _strip_tags(m.group(2), 160)
            if "duckduckgo.com" in href or len(title) < 8:
                continue
            out.append({"title": title, "url": href, "snippet": ""})
            if len(out) >= max_results:
                break
    return out


def _parse_bing(page: str, max_results: int) -> list[dict]:
    """Bing。注意：b_algo 块里的第一个 <a> 往往是 CSS 链接，
    真标题在 <h2><a> 里。抓错就会得到 "bytedance.com" 这种域名。"""
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', page, flags=re.S):
        block = m.group(0)
        # 必须先定位 h2，再从 h2 里取 a
        hm = re.search(r"<h2[^>]*>\s*<a[^>]+href=\"(https?://[^\"]+)\"[^>]*>(.*?)</a>", block, flags=re.S)
        if not hm:
            continue
        title = _strip_tags(hm.group(2), 200)
        if len(title) < 6:
            continue
        # 摘要：优先 b_caption 里的 p
        sm = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, flags=re.S)
        if not sm:
            sm = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.S)
        snippet = _strip_tags(sm.group(1), 500) if sm else ""
        out.append({"title": title, "url": hm.group(1), "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


# --------------------------------------------------------------------------
# 正规搜索 API（推荐用于交付；HTML 抓取始终脆弱）
# --------------------------------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict, timeout: int = 25) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _search_tavily(query: str, max_results: int) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY 未设置")
    data = _post_json("https://api.tavily.com/search",
                      {"api_key": key, "query": query, "max_results": max_results}, {})
    return [{"title": it.get("title", ""), "url": it.get("url", ""),
             "snippet": (it.get("content") or "")[:500]} for it in data.get("results", [])]


def _search_serper(query: str, max_results: int) -> list[dict]:
    key = os.getenv("SERPER_API_KEY")
    if not key:
        raise RuntimeError("SERPER_API_KEY 未设置")
    data = _post_json("https://google.serper.dev/search", {"q": query, "num": max_results},
                      {"X-API-KEY": key})
    return [{"title": it.get("title", ""), "url": it.get("link", ""),
             "snippet": (it.get("snippet") or "")[:500]} for it in data.get("organic", [])]


def _search_bocha(query: str, max_results: int) -> list[dict]:
    key = os.getenv("BOCHA_API_KEY")
    if not key:
        raise RuntimeError("BOCHA_API_KEY 未设置")
    data = _post_json("https://api.bochaai.com/v1/web-search",
                      {"query": query, "count": max_results, "summary": True},
                      {"Authorization": f"Bearer {key}"})
    pages = ((data.get("data") or {}).get("webPages") or {}).get("value", []) or []
    return [{"title": it.get("name", ""), "url": it.get("url", ""),
             "snippet": (it.get("summary") or it.get("snippet") or "")[:500]} for it in pages]


SEARCH_BACKENDS = [
    # 有 API Key 时优先走这里（稳定、可交付）
    ("tavily", "", _search_tavily),
    ("serper", "", _search_serper),
    ("bocha", "", _search_bocha),
    # 无 Key 时的免费兜底（HTML 抓取，脆弱但零成本）
    ("ddg-lite", "https://lite.duckduckgo.com/lite/?q={q}", _parse_ddg_lite),
    ("ddg-html", "https://html.duckduckgo.com/html/?q={q}", _parse_ddg),
    ("bing", "https://www.bing.com/search?q={q}&setlang=zh-CN", _parse_bing),
]
# 注：百度已移除 —— 实测直接返回"安全验证"反爬页，无法使用。
# 注：API 后端返回 (results) 而非 HTML，故 tpl 为空，由下方分支处理。


def web_search(query: str, max_results: int = 5, backend: str | None = None) -> dict:
    """联网搜索，多后端自动切换。

    实测可靠性（单后端连续搜索都会挂）：
      - DuckDuckGo：连续请求限流，实测 4 次挂 2 次
      - Bing：稳定但中文结果偏弱（多百科/官网首页）
      - 百度：直接反爬，已移除
      - Tavily / Serper / Bocha：正规 API，**企业交付应走这里**

    策略：从上次成功的后端开始试（粘性偏好），失败换下一个。
    """
    max_results = max(1, min(int(max_results or 5), 10))
    n = len(SEARCH_BACKENDS)
    if backend:
        order = [i for i, (nm, _, _) in enumerate(SEARCH_BACKENDS) if nm == backend]
        if not order:
            return {"ok": False, "backend": None, "results": [],
                    "error": f"未知后端 {backend}，可用: {[b[0] for b in SEARCH_BACKENDS]}"}
    else:
        order = [(_SEARCH_STATE["backend"] + i) % n for i in range(n)]
    errors: list[str] = []

    for idx in order:
        name, tpl, fn = SEARCH_BACKENDS[idx]
        try:
            if tpl:                                   # HTML 抓取型
                page = _get(tpl.format(q=urllib.parse.quote(query)), timeout=20)
                results = fn(page, max_results)
            else:                                     # API 型
                results = fn(query, max_results)
        except Exception as e:
            errors.append(f"{name}: {e}" if "未设置" in str(e) else f"{name}: {type(e).__name__}")
            continue

        if results:
            _SEARCH_STATE["backend"] = idx
            thin = sum(1 for r in results if len(r["title"]) + len(r.get("snippet", "")) < 60)
            quality = "low" if thin >= max(1, len(results) // 2) else "ok"
            return {"ok": True, "backend": name, "quality": quality, "results": results}
        errors.append(f"{name}: 无结果(可能限流)")

    return {"ok": False, "backend": None, "results": [],
            "error": "所有搜索后端都失败 -> " + "; ".join(errors)}


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
