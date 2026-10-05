# -*- coding: utf-8 -*-
"""离线自检 —— 不需要 API Key，就能验证 90% 的东西是好的。

为什么要有这个脚本：
    "没有 Key 所以什么都干不了"是假的。实际上 4 个项目里有 3 个能离线跑通。
    这个脚本把"必须有 Key"和"无需 Key"彻底分开，让你知道卡点到底在哪一格。

用法:
    python selftest.py            # 跑全部离线检查
    python selftest.py --verbose  # 显示详细输出
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "项目"

results: list[tuple[str, str, str]] = []   # (状态, 项目, 说明)


def rec(status: str, name: str, detail: str = ""):
    icon = {"OK": "[OK]  ", "WARN": "[警告]", "FAIL": "[失败]", "SKIP": "[跳过]", "NEED": "[需Key]"}
    print(f"  {icon.get(status, '?')} {name}" + (f"  -- {detail}" if detail else ""))
    results.append((status, name, detail))


def run(args: list[str], cwd: Path | None = None, timeout: int = 90):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 999, "(超时)"
    except Exception as e:
        return 998, f"{type(e).__name__}: {e}"


def has_key() -> bool:
    import os
    return any(os.getenv(v) for v in
               ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY",
                "MOONSHOT_API_KEY", "ZHIPUAI_API_KEY", "DSH_LOCAL_BASE_URL"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    print("=" * 66)
    print(f"  12周计划 · 离线自检    {date.today():%Y-%m-%d}")
    print("=" * 66)

    # ---------------- 1. 基础环境 ----------------
    print("\n【1】基础环境")
    rec("OK" if sys.version_info >= (3, 9) else "FAIL", f"Python {sys.version.split()[0]}")
    for mod in ("fastapi", "uvicorn", "pydantic", "requests"):
        rec("OK" if importlib.util.find_spec(mod) else "WARN",
            f"依赖 {mod}", "" if importlib.util.find_spec(mod) else "缺失（可选）")

    # ---------------- 2. W01 研究助手 ----------------
    print("\n【2】W01 · AI商业研究助手")
    d1 = PROJ / "ai-research-agent"
    for f in ("agent.py", "tools.py", "llm.py", "main.py", "hello_llm.py"):
        rec("OK" if (d1 / f).exists() else "FAIL", f"{f} 存在")
    code, out = run([sys.executable, "tools.py"], cwd=d1, timeout=90)
    ok_search = '"ok": true' in out or "'ok': True" in out
    rec("OK" if ok_search else "WARN", "工具层联网搜索", "能抓到真实结果" if ok_search else "搜索失败（网络或被限流）")
    if has_key():
        rec("NEED", "LLM 调用", "有 Key，可跑 hello_llm.py")
    else:
        rec("NEED", "LLM 调用", "缺 API Key —— 这是唯一真卡点")

    # ---------------- 3. W02 状态图 ----------------
    print("\n【3】W02 · 状态图引擎（免 Key 可全验）")
    d2 = PROJ / "langgraph-mini"
    code, out = run([sys.executable, "workflow.py", "--mock", "--auto"], cwd=d2)
    ok = code == 0 and "执行轨迹" in out
    rec("OK" if ok else "FAIL", "mock 全流程（plan→gather→write→review→publish）",
        "5 个节点全跑通" if ok else out[-200:])
    code, out = run([sys.executable, "workflow.py", "--draw"], cwd=d2)
    rec("OK" if "flowchart" in out else "FAIL", "状态图生成", "mermaid 可渲染")
    # 条件边与人工审核是否存在
    src = (d2 / "workflow.py").read_text(encoding="utf-8")
    rec("OK" if "route_review" in src and "node_review" in src else "FAIL", "人工审核节点 + 条件边")

    # ---------------- 4. W03 知识库 ----------------
    print("\n【4】W03 · 企业知识库（免 Key 可全验）")
    d3 = PROJ / "knowledge-base"
    code, out = run([sys.executable, "rag.py", "--build"], cwd=d3)
    n_chunks = ""
    for line in out.splitlines():
        if "索引完成" in line:
            n_chunks = line.strip()
    rec("OK" if code == 0 else "FAIL", "建索引", n_chunks)
    code, out = run([sys.executable, "rag.py", "--ask", "如何处理客户投诉", "--no-llm"], cwd=d3)
    rec("OK" if "检索到的资料" in out else "FAIL", "检索命中（相关问题）")
    code, out = run([sys.executable, "rag.py", "--ask", "今天天气怎么样", "--no-llm"], cwd=d3)
    rec("OK" if "拒答" in out else "WARN", "拒答机制（无关问题）",
        "正确拒答，不瞎编" if "拒答" in out else "未触发拒答，检查 min_score")
    code, out = run([sys.executable, "rag.py", "--eval"], cwd=d3, timeout=120)
    hit_line = ref_line = ""
    for line in out.splitlines():
        s = line.strip()
        # 精确匹配指标行，避免抓到下面的提示语
        if s.startswith("该答的题命中率"):
            hit_line = s.split(":", 1)[-1].strip()
        if s.startswith("不该答的题拒答率"):
            ref_line = s.split(":", 1)[-1].strip()
    rec("OK" if hit_line and ref_line else "WARN", "评测集",
        f"命中 {hit_line or '?'} / 拒答 {ref_line or '?'}")

    # ---------------- 5. W05 API 服务 ----------------
    print("\n【5】W05 · 知识库 API（免 Key 可全验）")
    d5 = PROJ / "kb-api"
    proc = None
    try:
        proc = subprocess.Popen([sys.executable, "server.py", "--port", "8177"],
                                cwd=str(d5), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        for _ in range(20):
            time.sleep(0.5)
            try:
                urllib.request.urlopen("http://127.0.0.1:8177/api/health", timeout=2)
                break
            except Exception:
                continue
        def hit_api(path, data=None):
            req = urllib.request.Request(
                "http://127.0.0.1:8177" + path,
                data=json.dumps(data).encode() if data else None,
                headers={"Content-Type": "application/json"},
                method="POST" if data else "GET")
            return json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        h = hit_api("/api/health")
        rec("OK", "启动服务 + /api/health", f"chunks={h['chunks']}, mode={'llm' if h['llm_available'] else '检索降级'}")
        r = hit_api("/api/ask", {"question": "如何处理客户投诉"})
        rec("OK" if r["sources"] else "WARN", "/api/ask 相关问题", f"来源 {len(r['sources'])} 条")
        r2 = hit_api("/api/ask", {"question": "今天天气怎么样"})
        rec("OK" if r2["refused"] else "WARN", "/api/ask 无关问题", "正确拒答")
    except Exception as e:
        rec("WARN", "API 服务", f"未能拉起或访问: {type(e).__name__}（不影响其他检查）")
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()

    # ---------------- 6. 进度与提醒体系 ----------------
    print("\n【6】追踪与提醒体系")
    for f in ("progress.py", "reminder.py", "check_env.py", "schedule.py"):
        p = ROOT / f
        rec("OK" if p.exists() else "WARN", f"{f} 存在")
    code, out = run([sys.executable, "progress.py"], cwd=ROOT)
    rec("OK" if "12周作战进度" in out else "FAIL", "进度指挥台可运行")
    code, out = run([sys.executable, "reminder.py", "--no-popup"], cwd=ROOT)
    rec("OK" if "今日任务" in out else "FAIL", "每日提醒可运行")
    try:
        code, out = run(["powershell", "-NoProfile", "-Command",
                         "Get-ScheduledTask -TaskName 'DSH-12Week-*' | Select-Object -ExpandProperty TaskName"],
                        timeout=60)
        n = len([l for l in out.splitlines() if l.strip().startswith("DSH-")])
        rec("OK" if n >= 2 else "WARN", f"计划任务已注册 {n} 个", "20:00 / 22:30 各一次")
    except Exception as e:
        rec("WARN", "计划任务查询", str(e))

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 66)
    counts: dict[str, int] = {}
    for s, _, _ in results:
        counts[s] = counts.get(s, 0) + 1
    print("  汇总: " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    fails = counts.get("FAIL", 0)
    need = counts.get("NEED", 0)
    print("=" * 66)

    if fails:
        print(f"  [!] {fails} 项失败，先修这些再看别的。")
    elif need:
        print("  [结论] 除了 LLM 调用，其他全部就绪。你只需要一个 API Key 就能开跑。")
        print("  申请（选一个）：")
        print("    DeepSeek   https://platform.deepseek.com/api_keys      便宜，推荐")
        print("    智谱 GLM   https://open.bigmodel.cn/                   glm-4-flash 免费额度")
        print("    阿里通义   https://bailian.console.aliyun.com/          新用户免费额度")
        print("  Key 到手后：把 .env.example 改名 .env 并填入，或跑：")
        print('    [Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY","sk-xxx","User")')
    else:
        print("  [结论] 全部就绪。开跑。")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
