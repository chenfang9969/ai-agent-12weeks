# -*- coding: utf-8 -*-
"""知识库 Agent 的 HTTP 服务层（W05 骨架）

为什么 W05 要这个东西：
    企业微信/飞书/网页都得通过 HTTP 才能连上你的 Agent。
    把这层标准化，三个入口就能共用同一套后端 —— 这就是"交付快"的秘密。

关键设计（也是你以后跟客户吹的底气）：
    **无 Key 也能跑。** 没有 LLM 时自动降级为"检索模式"，
    仍然返回原文片段+来源，只是不做自然语言总结。
    → 这意味着：Demo 演示不依赖网络和付费额度，现场演示不会翻车。

启动:
    python server.py                       # 默认 127.0.0.1:8100
    python server.py --port 8100 --host 0.0.0.0

调试:
    curl http://127.0.0.1:8100/api/health
    curl -X POST http://127.0.0.1:8100/api/ask -H "Content-Type: application/json" -d "{\"question\":\"如何处理客户投诉\"}"
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "knowledge-base"))
sys.path.insert(0, str(HERE.parent / "ai-research-agent"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import rag  # noqa: E402  (knowledge-base/rag.py)

app = FastAPI(
    title="企业知识库 Agent API",
    description="RAG 问答服务：检索 → 来源追溯 → 生成（无 Key 自动降级为检索模式）",
    version="0.5.0",
)
# 前端/企业微信回调会跨域，演示阶段先放开；正式交付要收紧到具体域名
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

INDEX = None
QA_LOG: deque = deque(maxlen=500)   # 内存版问答记录。真实交付要落库
STARTED_AT = time.time()


# --------------------------------------------------------------------------
# 数据模型
# --------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    top_k: int = Field(3, ge=1, le=10)
    min_score: float = Field(0.25, ge=0.0, le=5.0, description="相关度下限，越高越保守")
    no_llm: bool = Field(False, description="true=只返回检索片段，不调 LLM")


class Source(BaseModel):
    file: str
    section: str
    score: float
    excerpt: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]
    refused: bool = Field(..., description="true=资料里没找到，按设计拒答")
    mode: str = Field(..., description="llm=模型生成 / retrieval=检索模式")


class HealthResponse(BaseModel):
    status: str
    chunks: int
    llm_available: bool
    mode: str
    uptime_sec: int
    questions_asked: int


# --------------------------------------------------------------------------
# 核心逻辑
# --------------------------------------------------------------------------
def get_index():
    global INDEX
    if INDEX is None:
        try:
            INDEX = rag.load_index()
        except SystemExit:
            raise HTTPException(
                status_code=503,
                detail="索引不存在。先跑: python ../knowledge-base/rag.py --build",
            )
    return INDEX


def llm_available() -> bool:
    try:
        from llm import pick_provider
        pick_provider()
        return True
    except Exception:
        return False


def do_rag(question: str, top_k: int, min_score: float, no_llm: bool) -> dict:
    """一次完整问答。企业微信/网页/飞书三个入口都调这一个函数。"""
    idx = get_index()
    hits = rag.search(idx, question, top_k=top_k, min_score=min_score)

    if not hits:
        # ★ 拒答是产品能力，不是故障。企业客户最怕"一本正经地胡说"。
        return {
            "answer": "资料中没有找到相关内容，建议咨询相关同事。",
            "sources": [], "refused": True, "mode": "retrieval",
        }

    sources = [
        {"file": h["source"], "section": h["title"],
         "score": h["score"], "excerpt": h["text"][:200]}
        for h in hits
    ]

    if no_llm or not llm_available():
        body = "\n\n".join(
            f"【{i + 1}】{h['source']} · {h['title']}\n{h['text']}" for i, h in enumerate(hits)
        )
        return {"answer": f"（检索模式，未使用模型总结）\n\n{body}",
                "sources": sources, "refused": False, "mode": "retrieval"}

    return {"answer": rag.answer(question, hits, use_llm=True),
            "sources": sources, "refused": False, "mode": "llm"}


# --------------------------------------------------------------------------
# 路由
# --------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse)
def health():
    idx = get_index()
    ok = llm_available()
    return HealthResponse(
        status="ok",
        chunks=len(idx["chunks"]),
        llm_available=ok,
        mode="llm" if ok else "retrieval-only (未配置 API Key，功能降级但可用)",
        uptime_sec=int(time.time() - STARTED_AT),
        questions_asked=len(QA_LOG),
    )


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    t0 = time.time()
    r = do_rag(req.question, req.top_k, req.min_score, req.no_llm)
    QA_LOG.append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "question": req.question,
        "refused": r["refused"],
        "mode": r["mode"],
        "ms": int((time.time() - t0) * 1000),
    })
    return AskResponse(question=req.question, **r)


@app.get("/api/documents")
def documents():
    """列出知识库里的文档。后台管理页要用。"""
    idx = get_index()
    docs: dict[str, int] = {}
    for c in idx["chunks"]:
        docs[c["source"]] = docs.get(c["source"], 0) + 1
    return {"total_documents": len(docs),
            "documents": [{"name": k, "chunks": v} for k, v in sorted(docs.items())]}


@app.post("/api/reindex")
def reindex():
    """重新建索引。资料更新后一键同步（交付时写进操作手册）。"""
    global INDEX
    old = len(INDEX["chunks"]) if INDEX else 0
    INDEX = None
    idx = get_index()
    return {"ok": True, "chunks_before": old, "chunks_after": len(idx["chunks"])}


@app.get("/api/logs")
def logs(limit: int = 50):
    """问答记录。后台管理页要用 —— 客户最想看的就是"用户都问了什么"。"""
    items = list(QA_LOG)[-limit:]
    refused = sum(1 for x in items if x["refused"])
    return {"count": len(items), "refused": refused, "items": items,
            "note": "refused 高说明资料有缺口，这就是要补资料的地方"}


@app.get("/")
def root():
    return {
        "name": "企业知识库 Agent API",
        "version": "0.5.0",
        "endpoints": {
            "GET  /api/health": "健康检查 + 当前模式",
            "POST /api/ask": "提问（核心接口，三个入口都调它）",
            "GET  /api/documents": "文档清单",
            "POST /api/reindex": "重建索引",
            "GET  /api/logs": "问答记录",
            "GET  /docs": "FastAPI 自动生成的接口文档（可以直接演示给客户看）",
        },
    }


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    a = ap.parse_args()

    ok = llm_available()
    print("=" * 64)
    print("  企业知识库 Agent API")
    print("=" * 64)
    print(f"  模式: {'LLM 生成' if ok else '检索模式（未配置 API Key，仍可演示）'}")
    print(f"  地址: http://{a.host}:{a.port}")
    print(f"  文档: http://{a.host}:{a.port}/docs")
    print("=" * 64)
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
