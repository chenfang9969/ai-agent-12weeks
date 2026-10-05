# kb-api —— 知识库 Agent 的 HTTP 服务层（W05 骨架）

把 W03 的知识库包成 API，让**企业微信 / 飞书 / 网页**三个入口共用同一个后端。
W05 的任务就是接上其中一个入口，这层不用重写。

## 一个重要的设计决策

> **没有 API Key 也能跑。** 没有 LLM 时自动降级为"检索模式"：仍返回原文片段 + 来源，
> 只是不做自然语言总结。

为什么这个设计值钱：
1. **现场演示不会翻车** —— 客户会议室网络差、额度用完，你的 Demo 照样能演示
2. **成本可控** —— 内部测试阶段不烧钱
3. **诚实** —— 接口明确告诉你当前是哪种模式，不假装

## 接口清单

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 健康检查 + 当前模式（`llm` 还是 `retrieval`）|
| POST | `/api/ask` | **核心接口**，三个入口都调它 |
| GET | `/api/documents` | 文档清单（后台管理页用）|
| POST | `/api/reindex` | 资料更新后一键重建索引 |
| GET | `/api/logs` | 问答记录（客户最想看"用户都问了什么"）|
| GET | `/docs` | FastAPI 自动生成的接口文档，**可直接演示给客户看** |

## 运行

```powershell
cd D:\DeepSeekHarness\12周计划\项目\kb-api

# 前置：先建好知识库索引
python ..\knowledge-base\rag.py --build

python server.py                      # http://127.0.0.1:8100
python server.py --port 8200          # 换端口
python server.py --host 0.0.0.0       # 允许局域网访问（手机/其他机器测试用）
```

## 自测

```powershell
# 健康检查
curl http://127.0.0.1:8100/api/health

# 提问
curl -X POST http://127.0.0.1:8100/api/ask `
     -H "Content-Type: application/json" `
     -d "{\"question\":\"如何处理客户投诉\"}"

# 看问答记录（refused 高 = 资料有缺口 = 要补资料）
curl http://127.0.0.1:8100/api/logs
```

## W05 从这里继续

```
用户 → 企业微信/网页 → kb-api (/api/ask) → 知识库检索 → 返回
                              ↑
                    你只需要写"入口适配层"：
                    - 企业微信：接收回调 → 调 do_rag() → 回复消息
                    - 网页：React 前端 fetch /api/ask
                    - 飞书：同企业微信
```

**入口适配层不要改 `do_rag()`** —— 三个入口共用同一套问答逻辑，这是以后能快速交付多客户的关键。

## 交付前必须收紧的地方（现在故意放宽了）

- [ ] CORS `allow_origins=["*"]` → 改成客户的具体域名
- [ ] `QA_LOG` 是内存的，重启就丢 → 落库（SQLite 起步就够）
- [ ] 没有鉴权 → 加 API Key 或企业微信签名校验
- [ ] 没有限流 → 防止被刷爆额度
- [ ] 没有按部门隔离资料权限 → 真实企业必需
