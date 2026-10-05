# W01｜Agent 核心机制（2026-10-06 周二 ~ 10-12 周日）

> 本周唯一目标：**从"调 API 的人"变成"造循环的人"。**
> 验收标准：你能用自己的话讲清 Agent Loop，并且 v0.1 能跑出一个真实报告。

---

## 一、学习目标（原计划）

**1. Agent Loop** —— 必须能默画这条链：

```
目标 Goal
  ↓
思考 Reasoning   ← LLM 在这里决定下一步
  ↓
行动 Action      ← LLM 输出"我要调用哪个工具、参数是什么"
  ↓
工具 Tool        ← 你的代码真正执行（联网/查库/写文件）
  ↓
观察 Observation ← 执行结果塞回上下文
  ↓
回到 思考（直到 LLM 说"够了，给答案"）
```

**2. Tool Calling** —— 理解 Agent 凭什么能「搜索网页 / 查数据库 / 调 API / 操作文件」：
> 本质：LLM 不执行任何东西，它只是**输出一段结构化文本**（工具名+参数）。
> 真正干活的是你的 Python。这个认知想通了，你就理解了 90% 的 Agent 框架。

**3. 基础 ReAct 思想** —— 不手写框架，但要回答："Agent 为什么能完成一个没人教过它的任务？"

---

## 二、实践任务：AI 商业研究助手 v0.1

输入一句：`分析某公司 AI 战略` → Agent 自主：拆解 → 调工具 → 整理 → 出报告。

**你已有的底牌**：Python 熟练 + 在做 AI 商业研究公众号 → 这个 Agent 做完直接能用在你自己的内容生产上，不是玩具。

---

## 三、每日拆解（每天只做 3 步，60~90 分钟）

### Day 1 · 10/06（周二）— 环境 + 第一次裸调 LLM
```powershell
# 步骤 1：验证环境（5 分钟）
python D:\DeepSeekHarness\12周计划\check_env.py

# 步骤 2：没有 key 就配一个（10 分钟）
$env:DEEPSEEK_API_KEY="sk-你的key"
# 要永久生效：
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY","sk-你的key","User")

# 步骤 3：做"不叫 Agent"的裸调用，先确认能通
python D:\DeepSeekHarness\12周计划\项目\ai-research-agent\hello_llm.py
```
**今日验收**：终端打印出模型的一段回复。
**今日 30 分钟记录**：LLM API 调用和普通函数调用，本质区别是什么？

---

### Day 2 · 10/07（周三）— 手写工具层（最关键的一天）
读代码：`项目/ai-research-agent/tools.py`
- `web_search` 怎么把网页变成结构化结果？
- `web_fetch` 为什么要截断字数？（提示：token = 钱）
- 如果让你加第 4 个工具 `query_database`，接口该长什么样？

**动手**：给 `tools.py` 加一个你自己的工具（推荐：`write_note` 改成写进你公众号的素材库目录）。
**今日验收**：`python tools.py` 能打印出真实搜索结果。
**今日 30 分钟记录**：一个"工具"要满足什么条件，LLM 才能正确使用它？

---

### Day 3 · 10/08（周四）— 手写 Agent Loop（本阶段核心）
读代码：`项目/ai-research-agent/agent.py` 的 `research()` 循环。
**关键理解**：整个 Agent 就是这个 `while` 循环 + 一个 messages 列表。
**动手实验（必须做）**：把 `max_steps` 从 10 改成 2，再跑一次，观察报告质量怎么塌。
> 这个实验能让你彻底明白：**Agent 的能力上限 = 循环次数 × 工具质量**。

**今日验收**：能画出自己版本的流程图（不是抄的）。
**今日 30 分钟记录**：为什么上下文会越来越长？这是 Agent 最大的成本陷阱吗？

---

### Day 4 · 10/09（周五）— 跑通 v0.1
```powershell
python D:\DeepSeekHarness\12周计划\项目\ai-research-agent\main.py "分析字节跳动的AI战略"
```
**今日验收**：`output/` 下生成一份中文 md 报告，且**工具调用日志显示它真的搜了网页**（不是你编的）。
**今日 30 分钟记录**：这份报告里，哪些内容是模型瞎编的？怎么发现？怎么防？

---

### Day 5 · 10/10（周六）— 换成你的真实业务问题
换 3 个输入各跑一次，其中至少 1 个是**你公众号真正要写的选题**。
建立 `output/` → 你自己内容工作流的通路。
**今日验收**：3 份报告 + 一句话结论：它省了我多少时间？
**今日 30 分钟记录**：这个 Agent 的商业价值，对我自己 / 对我的读者，分别是什么？

---

### Day 6 · 10/11（周日）— 封装 + 补文档
1. 初始化 Git 仓库并首次提交（这是你 GitHub 项目的起点）
2. 补 README（项目结构 + 架构图 + 用法 + 已知缺陷）
3. 补 `docs/agent-flow.md`（Agent 流程图，Mermaid）
4. 21:00 填 `周复盘/W01-复盘.md`

> **Git 仓库我已经替你初始化好了**（这就是 Day 6 的前半件事）：
> ```powershell
> cd D:\DeepSeekHarness\12周计划
> git log --oneline            # 应看到 2e7677f W01: AI商业研究助手 v0.1 + 12周作战体系
> git ls-files | Measure-Object -Line   # 43 个文件已入库
> ```
> `.gitignore` 已排除 `__pycache__` / `.env` / `output/产物` / `index.json`，
> 并确认过**没有任何密钥或产物被提交**。`.gitattributes` 统一了行尾，`git status` 保持干净。

**你今天要做的只剩"推上 GitHub"这一步：**
```powershell
# 1) 在 https://github.com/new 建一个**空**仓库（不要勾 README/gitignore）
# 2) 关联并推送（把 URL 换成你自己的）
git remote add origin https://github.com/<你的用户名>/ai-agent-12weeks.git
git branch -M main
git push -u origin main
# 3) 认证方式：GitHub 已不支持密码，用 Personal Access Token
#    生成: https://github.com/settings/tokens  (勾 repo 权限)
```
> 推上去之后，你就有了计划要求的第一个资产：**GitHub 项目**。
> 仓库名建议 `ai-agent-12weeks` —— 面试或见客户时可直接给链接。

**今日验收**：`git log` 有第一条提交，README 能让陌生人 10 分钟跑起来，GitHub 上能看到仓库。

---

## 四、周末产出（原计划验收清单）

- [ ] 项目代码，能跑，在自己电脑上可复现
- [ ] README
- [ ] Agent 流程图（能讲给别人听的那种）

## 五、本周埋伏的"商业线索"（提前种，W8 收）

做 v0.1 的过程中，随手记下：**谁会需要"自动出研究报告"这件事？**
- 投资/券商分析师？咨询公司？企业战略部？自媒体同行？
- 写进 `周复盘/W01-复盘.md` 最后一节，一个名字一行。

## 六、本周不做什么（防跑偏）

- ❌ 不学 LangChain / LangGraph（第 2 周的事，别提前）
- ❌ 不搭 RAG、不接向量库（第 3 周）
- ❌ 不做前端界面。v0.1 命令行就是终点。丑的能跑 > 美的不能跑
