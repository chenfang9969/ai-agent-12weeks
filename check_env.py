# -*- coding: utf-8 -*-
r"""环境自检 —— 第1周第一步跑这个。
用法:  python "D:\DeepSeekHarness\12周计划\check_env.py"
"""
import importlib
import os
import sys
import urllib.request

try:  # Windows 控制台默认 GBK，不切 UTF-8 会乱码/崩
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 本项目刻意零第三方依赖：HTTP 调用走标准库 urllib，HTML 用正则清洗。
# 只有这两个是"可选加速"，没有也能跑。
NEED = ["requests", "bs4"]
KEY_VARS = [
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("ZHIPUAI_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
]


def hr(t):
    print("\n" + "=" * 56)
    print(t)
    print("=" * 56)


def main():
    ok = True

    hr("1. Python")
    print("版本 :", sys.version.split()[0], "|", sys.executable)
    if sys.version_info < (3, 9):
        print("[X] 需要 Python 3.9+")
        ok = False
    else:
        print("[OK]")

    hr("2. 依赖包")
    for m in NEED:
        try:
            importlib.import_module(m)
            print(f"[OK]   {m}")
        except ImportError:
            print(f"[MISS] {m}   ->  pip install {m}")
            ok = False

    hr("3. LLM API Key")
    # 先尝试从 .env 读取（放在项目目录或 12周计划 根目录都行）
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        for p in (Path(__file__).resolve().parent / ".env",
                  Path(__file__).resolve().parent / "项目" / "ai-research-agent" / ".env"):
            if p.exists():
                load_dotenv(p, override=False)
                print(f"[.env] 已加载 {p}")
    except ImportError:
        pass

    found = []
    for var, base, model in KEY_VARS:
        v = os.getenv(var)
        if v:
            print(f"[OK]   {var} = {v[:6]}...{v[-4:]}  ({len(v)} 字符)")
            found.append((var, base, model))
        else:
            print(f"[--]   {var} 未设置")
    if not found:
        print("\n[!] 一个 key 都没有。选一个：")
        print('    $env:DEEPSEEK_API_KEY="sk-xxxx"          # 临时，当前窗口有效')
        print('    [Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY","sk-xxxx","User")   # 永久')
        print("    申请: https://platform.deepseek.com/api_keys")
    else:
        print(f"\n[OK] 共 {len(found)} 个可用 key，将优先使用 {found[0][0]}")

    hr("4. 联网能力（搜索抓取靠它）")
    try:
        req = urllib.request.Request(
            "https://duckduckgo.com/", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print("[OK] 外网可达, HTTP", r.status)
    except Exception as e:
        print("[!] 外网请求失败:", type(e).__name__, e)
        print("    tools.py 的 web_search 会失效。可换必应/自建搜索，或先只用 web_fetch。")

    hr("5. 结论")
    print("[OK] 环境就绪，去跑:  python 项目\\ai-research-agent\\hello_llm.py" if ok
          else "[!] 先把上面标 [MISS] 的补上，再继续。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
