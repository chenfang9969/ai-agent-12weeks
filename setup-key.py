# -*- coding: utf-8 -*-
"""一键配置 API Key —— 不用打开编辑器，粘贴 + 回车即可。

用法:
    python "D:\\DeepSeekHarness\\12周计划\\setup-key.py"
    python setup-key.py --provider DASHSCOPE_API_KEY     # 换别的供应商
    python setup-key.py --check                          # 只检查当前配置并实测连通

为什么要有这个脚本：
    手动打开 .env 删除中文占位符，是最容易出错的一步（占位符删不干净就会报错）。
    这个脚本直接输入 Key，自动写对格式，并立刻发一次真实请求验证。
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"

PROVIDERS = {
    "DEEPSEEK_API_KEY": ("https://api.deepseek.com/v1", "deepseek-chat", "DeepSeek"),
    "DASHSCOPE_API_KEY": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", "阿里通义"),
    "MOONSHOT_API_KEY": ("https://api.moonshot.cn/v1", "moonshot-v1-8k", "Kimi/月之暗面"),
    "ZHIPUAI_API_KEY": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", "智谱 GLM"),
    "OPENAI_API_KEY": ("https://api.openai.com/v1", "gpt-4o-mini", "OpenAI"),
}

BANNER = """
==============================================================
  一键配置 API Key
==============================================================
  粘贴时会隐藏输入（这是正常的，不是卡住了）。
  粘贴后按回车即可。
--------------------------------------------------------------"""


def mask(v: str) -> str:
    if len(v) <= 12:
        return v[:4] + "..." + v[-2:]
    return f"{v[:7]}...{v[-4:]}  ({len(v)} 字符)"


def read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV.exists():
        return out
    for line in ENV.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def write_env(data: dict[str, str]):
    """完整重写 .env，保留注释头。"""
    header = (
        "# 本地密钥文件 —— 已被 .gitignore 排除，绝不会进 git\n"
        "# 由 setup-key.py 自动写入。改 Key 直接重跑 setup-key.py 即可。\n\n"
    )
    body = "\n".join(f"{k}={v}" for k, v in data.items() if v)
    ENV.write_text(header + body + "\n", encoding="utf-8")


def test_key(provider: str, key: str) -> tuple[bool, str]:
    """发一次最小真实请求，验证 Key 是否真的可用。"""
    base, model, name = PROVIDERS[provider]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "只回四个字：连接成功"}],
        "temperature": 0,
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage") or {}
        return True, f"{name} / {model} 回复: {text}  (tokens: {usage.get('total_tokens', '?')})"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")[:200]
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def do_check() -> int:
    data = read_env()
    if not data:
        print(f"[X] {ENV} 不存在或为空。跑一次不带参数的 setup-key.py 来配置。")
        return 1
    ok_any = False
    for k, v in data.items():
        if k not in PROVIDERS:
            continue
        print(f"[配置] {k} = {mask(v)}")
        ok, msg = test_key(k, v)
        print(f"       {'[可用]' if ok else '[失败]'} {msg}")
        ok_any = ok_any or ok
    if not ok_any:
        print("\n[X] 没有一个可用的 Key。检查是否复制完整、有没有多余空格。")
        return 1
    print("\n[OK] 配置可用。下一步:  python 项目\\ai-research-agent\\hello_llm.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="一键配置 API Key")
    ap.add_argument("--provider", default="DEEPSEEK_API_KEY",
                    choices=list(PROVIDERS), help="要配置哪个供应商")
    ap.add_argument("--check", action="store_true", help="只检查现有配置并实测")
    a = ap.parse_args()

    if a.check:
        return do_check()

    base, model, name = PROVIDERS[a.provider]
    print(BANNER)
    print(f"  供应商: {name}   默认模型: {model}")
    print(f"  写入位置: {ENV}")
    print("=" * 62)

    if not ENV.parent.exists():
        ENV.parent.mkdir(parents=True, exist_ok=True)

    # 非交互终端（管道/重定向）下不要用 getpass，否则会一直等输入挂住
    if not sys.stdin.isatty():
        print("\n[X] 当前不是交互式终端，无法安全地隐藏输入。")
        print(f"    请直接编辑这个文件填入 Key: {ENV}")
        print("    或改跑:  python setup-key.py --check   （只检查现有配置）")
        return 1

    try:
        key = getpass.getpass("\n请粘贴你的 API Key 然后回车: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[取消] 未做任何修改")
        return 1

    key = key.strip().strip('"').strip("'")
    if not key:
        print("[X] 输入为空。")
        return 1
    if len(key) < 20:
        print(f"[X] 这个值太短了（{len(key)} 字符），像是复制不全。Key 一般 30 字符以上。")
        return 1
    if any(x in key for x in ("在这里", "你的", "xxxx", "粘贴")):
        print("[X] 你还是把中文占位符粘进来了。要粘的是那串 sk- 开头的真实字符。")
        return 1

    print(f"\n[输入] {mask(key)}")
    print("[验证] 正在发一次真实请求 ...")
    ok, msg = test_key(a.provider, key)
    if not ok:
        print(f"[失败] {msg}")
        print("\n没写入。请检查：")
        print("  1. Key 是否复制完整（前后无空格、无多余引号）")
        print("  2. 是否已在该平台完成实名/开通（有些平台要先开通才可用）")
        print("  3. 网络是否需要代理")
        return 1

    print(f"[成功] {msg}")

    data = read_env()
    data[a.provider] = key
    write_env(data)
    print(f"\n[已写入] {ENV}")
    print("[安全]  该文件已被 .gitignore 忽略，不会进 git / GitHub")

    # 顺手确认 git 忽略生效
    try:
        import subprocess
        r = subprocess.run(["git", "check-ignore", "-q", str(ENV)], cwd=str(ROOT), timeout=20)
        print(f"[安全]  git 忽略检查: {'通过' if r.returncode == 0 else '未通过，请告知我'}")
    except Exception:
        pass

    print("\n" + "=" * 62)
    print("  下一步（Day 1 验收）:")
    print('    python "D:\\DeepSeekHarness\\12周计划\\项目\\ai-research-agent\\hello_llm.py"')
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
