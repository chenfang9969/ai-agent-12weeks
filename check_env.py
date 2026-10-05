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


def is_placeholder(v: str) -> bool:
    """识别占位符 / 明显无效的 Key，避免误报“已配置”。"""
    if not v:
        return True
    bad = ("在这里", "你的", "your", "xxxx", "paste", "粘贴", "sk-xxx")
    low = v.lower()
    return any(b in low for b in bad) or len(v) < 20


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

    hr("3. 模型配置（三选一：云端 Key / 免费额度 / 本地模型）")
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
    placeholders = []
    for var, base, model in KEY_VARS:
        v = os.getenv(var)
        if not v:
            print(f"[--]   {var} 未设置")
        elif is_placeholder(v):
            print(f"[占位] {var} 还是占位符，必须换成真实 Key（当前值: {v}）")
            placeholders.append(var)
        else:
            print(f"[OK]   {var} = {v[:6]}...{v[-4:]}  ({len(v)} 字符)")
            found.append((var, base, model))

    local = os.getenv("DSH_LOCAL_BASE_URL")
    if local:
        print(f"[OK]   本地模型 {local}  模型={os.getenv('DSH_LOCAL_MODEL', 'qwen2.5:7b')}")
        found.append(("DSH_LOCAL_BASE_URL", local, os.getenv("DSH_LOCAL_MODEL", "qwen2.5:7b")))

    if not found:
        print("\n[!] 没有配置任何模型。三条路选一条：")
        print('  A 云端(推荐): $env:DEEPSEEK_API_KEY="sk-xxxx"       https://platform.deepseek.com/api_keys')
        print('  B 免费额度  : 智谱 glm-4-flash 免费                  https://open.bigmodel.cn/')
        print('                阿里通义 新用户免费额度                https://bailian.console.aliyun.com/')
        print('  C 本地模型  : $env:DSH_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"')
        print("                本机 Intel 核显 + 16G 内存，会很慢，仅作备选")
        print("  配一次长期有效：把 .env.example 复制成 .env 并填入")
    else:
        print(f"\n[OK] 共 {len(found)} 个可用来源，将优先使用 {found[0][0]}")

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
    if not ok:
        print("[X] 依赖没装齐，先补上面标 [MISS] 的，再继续。")
        return 1
    if found:
        print(f"[OK] 全部就绪，模型来源: {found[0][0]}")
        print("     去跑:  python 项目\\ai-research-agent\\hello_llm.py")
        return 0
    # 依赖齐了但没模型：这是"差一步"，不能说成就绪
    print("[!] 还差最后一步：没有可用的模型来源。")
    if placeholders:
        print(f"    检测到占位符: {', '.join(placeholders)}")
        print("    打开 D:\\DeepSeekHarness\\12周计划\\.env ，把 sk-在这里粘贴你的真实Key")
        print("    替换成你的真实 Key，保存后再跑一次本脚本。")
    else:
        print("    打开 .env 填入 Key，或按上面 A/B/C 三条路任选一条。")
    print("    其余一切（代码/项目/工具/进度体系）都已就绪。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
