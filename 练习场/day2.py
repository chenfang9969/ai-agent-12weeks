# -*- coding: utf-8 -*-
r"""练习 2：自己写一个工具，并把它"注册"进去（约 20 分钟）

跑法:  python "D:\DeepSeekHarness\12周计划\练习场\day2.py"

为什么练这个：
    你今天说"不明白注册和工具调用的实际原理"。其实整件事只有三步：
        ① 写函数          —— 代码里有了这个能力
        ② 写进 TOOL_SPECS —— 模型"看到"有这个工具
        ③ 写进 REGISTRY   —— 代码知道该调哪个函数
    这个练习就是让你把这三步亲手走一遍，全程不看 tools.py。

规则：
    不许打开 项目\ai-research-agent\tools.py。凭记忆写。
    卡住超过 10 分钟再看提示。写丑没关系，测试过了就算过。
"""
from __future__ import annotations

import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ===========================================================================
# 第 ① 步：写两个工具函数（照今天的 time_data 那个样子写）
# ===========================================================================
# 1. word_count：数一段文字有多少个词（按空格切开数）
#    例：word_count("hello world foo") 应该返回 3
#    返回值格式必须和别的工具一致：{"ok": True, ...}
def word_count(text: str) -> dict:
    # TODO: 请在这里写
    return {"ok":True,"count":len(text.split())}
    pass


# 2. make_slug：把标题转成"网址安全的短名"
#    规则：空格换成 "-"，只保留字母数字和"-"，全部转小写
#    例：make_slug("Hello World 2026") 应该返回 "hello-world-2026"
#    提示：可以分几步做；也可以只保留需要的字符
def make_slug(title: str) -> dict:
    # TODO: 请在这里写
    return {"ok":True,"slug":title.lower().replace(" ", "-")}
    pass


# ===========================================================================
# 第 ② 步：写"给模型看的菜单"
#    每个工具要有 name / description / parameters
#    description 要写清楚：这工具干什么、什么时候该用它
# ===========================================================================
TOOL_SPECS = [
    # TODO: 在这里补两个字典，对应上面两个工具
    # 格式参考（这是示例，你要换成上面两个工具的真实信息）：
    # {
    #     "name": "工具名，必须和 REGISTRY 里的键完全一致",
    #     "description": "这工具干什么。什么情况下该用它。",
    #     "parameters": {"参数名": "参数的说明"},
    # }
    {
        "name":"word_count",
        "description":"数一段文字有多少个词（按空格切开数）",
        "parameters":{"text":"要数词的文字"},
    },
    {
        "name":"make_slug",
        "description":"把标题转成\"网址安全的短名\"",
        "parameters":{"title":"标题"},
    },
]


# ===========================================================================
# 第 ③ 步：写"给代码用的电话簿"
#    键 = 工具名（必须和 TOOL_SPECS 里的 name 一模一样）
#    值 = 上面写的函数本身（注意：不加括号）
# ===========================================================================
REGISTRY = {
    # TODO: 把两个工具注册进来，例如 "word_count": word_count,
    "word_count":word_count,"make_slug":make_slug
}


# ===========================================================================
# 下面这段是"模拟模型调用工具"的过程 —— 别改，但你要读懂它在干嘛
# ===========================================================================
def simulate_model_call(tool_name: str, params: dict) -> dict:
    """模拟 agent.py 里 execute() 做的事。

    真实流程是：模型输出 {"tool": "...", "input": {...}}
              -> 拿 tool 去 REGISTRY 查 -> 查到就调 -> 结果喂回模型
    """
    fn = REGISTRY.get(tool_name)
    if fn is None:
        # 注意这里：失败时把"可用工具列表"一起返回 —— 这就是今天说的
        # "错误信息也是提示词"
        return {"ok": False, "error": f"未知工具 {tool_name}，可用: {list(REGISTRY)}"}
    try:
        return fn(**params)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def to_prompt_text() -> str:
    """模拟 as_prompt()：把 TOOL_SPECS 渲染成给模型看的文字。"""
    lines = ["你可以调用以下工具（每次只能调用一个）：", ""]
    for t in TOOL_SPECS:
        lines.append(f"### {t.get('name')}")
        lines.append(t.get("description", ""))
        for k, v in (t.get("parameters") or {}).items():
            lines.append(f"  - {k}: {v}")
        lines.append("")
    return "\n".join(lines)


# ===========================================================================
# 自动批改 —— 跑这个文件就会检查你写得对不对
# ===========================================================================
def _run_tests() -> int:
    checks: list[tuple[str, bool, str]] = []

    # --- 第 ① 步：函数本身 ---
    r = word_count("hello world foo")
    checks.append(("word_count('hello world foo')",
                   isinstance(r, dict) and r.get("count") == 3,
                   f"你得到 {r!r}，期望 dict 且 count=3"))

    r = word_count("")
    checks.append(("word_count('')",
                   isinstance(r, dict) and r.get("count") == 0,
                   f"你得到 {r!r}，期望 count=0"))

    r = make_slug("Hello World 2026")
    checks.append(("make_slug('Hello World 2026')",
                   isinstance(r, dict) and r.get("slug") == "hello-world-2026",
                   f"你得到 {r!r}，期望 slug='hello-world-2026'"))

    r = make_slug("  A  B  ")
    checks.append(("make_slug('  A  B  ')",
                   isinstance(r, dict) and r.get("slug") in ("a-b", "a--b"),
                   f"你得到 {r!r}，期望 'a-b' 或 'a--b'（多余空格无所谓）"))

    # --- 第 ② 步：TOOL_SPECS ---
    spec_names = [t.get("name") for t in TOOL_SPECS]
    checks.append(("TOOL_SPECS 有 2 条",
                   len(TOOL_SPECS) == 2, f"现在是 {len(TOOL_SPECS)} 条"))
    checks.append(("TOOL_SPECS 名字是 word_count / make_slug",
                   set(spec_names) == {"word_count", "make_slug"},
                   f"现在是 {spec_names}"))
    checks.append(("每条都有非空 description",
                   len(TOOL_SPECS) > 0
                   and all(len(str(t.get("description", "")).strip()) >= 8 for t in TOOL_SPECS),
                   "有条目的 description 太短或为空 —— 模型看不懂就不会用"))

    # --- 第 ③ 步：REGISTRY ---
    checks.append(("REGISTRY 键是 word_count / make_slug",
                   set(REGISTRY.keys()) == {"word_count", "make_slug"},
                   f"现在是 {list(REGISTRY.keys())}"))
    checks.append(("REGISTRY 的值是函数本身",
                   all(callable(v) for v in REGISTRY.values()),
                   "值必须是函数（不能加括号、不能是调用结果）"))

    # --- 关键一致性检查：两张表名字必须完全一致 ---
    # 注意：两张表都空的时候也算"一致"，那是假通过，所以要求非空
    same = bool(spec_names) and set(spec_names) == set(REGISTRY.keys())
    checks.append(("★ TOOL_SPECS 与 REGISTRY 名字完全一致（最重要）", same,
                   f"菜单写的是 {spec_names}，电话簿写的是 {list(REGISTRY.keys())}"))

    # --- 模拟模型调用 ---
    if same and len(REGISTRY) == 2:
        r1 = simulate_model_call("word_count", {"text": "a b c d"})
        checks.append(("模拟调用 word_count 成功",
                       r1.get("ok") is True and r1.get("count") == 4,
                       f"返回 {r1!r}"))
        r2 = simulate_model_call("make_slug", {"title": "My Post Title"})
        checks.append(("模拟调用 make_slug 成功",
                       r2.get("ok") is True and r2.get("slug") == "my-post-title",
                       f"返回 {r2!r}"))
        r3 = simulate_model_call("not_exist", {})
        checks.append(("调用不存在的工具会返回可用列表（错误信息也是提示词）",
                       r3.get("ok") is False and "可用" in str(r3.get("error", "")),
                       f"返回 {r3!r}"))
    else:
        checks.append(("模拟调用（依赖上面两张表一致）", False, "先把两张表的名字写一致"))

    # --- 给模型看的菜单文本 ---
    p = to_prompt_text()
    checks.append(("菜单文本里包含两个工具说明",
                   "word_count" in p and "make_slug" in p, "菜单文本不完整"))

    # ---------------- 输出 ----------------
    print("=" * 66)
    print("  练习 2 · 工具注册机制 · 自动批改")
    print("=" * 66)
    passed = 0
    for name, ok, detail in checks:
        if ok:
            passed += 1
            print(f"  [通过] {name}")
        else:
            print(f"  [未过] {name}")
            print(f"         {detail}")
    total = len(checks)
    print("-" * 66)
    print(f"  得分: {passed}/{total}")
    if passed == total:
        print("  [完成] 你亲手把'写函数 -> 写菜单 -> 注册'三步走通了。")
        print("         现在你明白 time_date 当初为什么能生效了。")
    else:
        print("  [继续] 把标 [未过] 的改掉再跑。")
    print("=" * 66)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(_run_tests())
