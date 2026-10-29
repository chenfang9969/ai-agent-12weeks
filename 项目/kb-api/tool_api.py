# -*- coding: utf-8 -*-
"""业务工具 API（W04 演示用）

用途：给 Dify 的 HTTP 请求节点/自定义工具调用，模拟"查库存""查订单"。

为什么要有这一层：
    企业知识库只能回答"资料里写了什么"，
    回答不了"现在还有几台库存"——那是实时数据，必须查系统。
    所以真实交付里，Agent = 知识库（静态资料）+ 工具接口（实时数据）。

启动：
    python tool_api.py                 # 127.0.0.1:8200
    python tool_api.py --host 0.0.0.0  # 允许 Docker 容器访问

接口：
    GET /api/health                    健康检查
    GET /api/stock?sku=X1-BASIC        查库存
    GET /api/order?order_id=SO2026001  查订单
    GET /docs                         自动生成的接口文档（可直接演示给客户）
"""
from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = FastAPI(
    title="企业业务工具 API",
    description="给 AI Agent 调用的业务接口（库存 / 订单）",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 模拟数据（真实项目里换成查数据库）
# ---------------------------------------------------------------------------
STOCK = {
    "X1-BASIC": {"name": "智能客服机器人 X1 基础版", "stock": 42, "unit": "套", "price": 3800},
    "X1-STD": {"name": "智能客服机器人 X1 标准版", "stock": 13, "unit": "套", "price": 9800},
    "X1-ENT": {"name": "智能客服机器人 X1 企业版", "stock": 0, "unit": "套", "price": 24000},
    "HW-DOOR": {"name": "门禁道闸一体机", "stock": 7, "unit": "台", "price": 6500},
}

ORDERS = {
    "SO2026001": {"status": "已发货", "carrier": "顺丰", "tracking": "SF1234567890",
                  "sku": "X1-BASIC", "qty": 2, "eta": "2026-10-30"},
    "SO2026002": {"status": "待发货", "carrier": "-", "tracking": "-",
                  "sku": "X1-STD", "qty": 1, "eta": "2026-10-31"},
    "SO2026003": {"status": "已签收", "carrier": "京东物流", "tracking": "JD987654321",
                  "sku": "HW-DOOR", "qty": 3, "eta": "2026-10-25"},
}


class StockResp(BaseModel):
    ok: bool
    sku: str
    name: str
    stock: int
    unit: str
    price: float
    in_stock: bool
    message: str


class OrderResp(BaseModel):
    ok: bool
    order_id: str
    status: str
    carrier: str
    tracking: str
    sku: str
    qty: int
    eta: str


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "skus": len(STOCK), "orders": len(ORDERS)}


@app.get("/api/stock", response_model=StockResp)
def get_stock(sku: str = Query(..., description="产品编码，例如 X1-BASIC")):
    """查库存。没有这个 SKU 时返回 404 + 可用列表（错误信息也要能指导下一步）。"""
    key = sku.strip().upper()
    item = STOCK.get(key)
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"没有这个产品编码：{sku}。可用的有：{', '.join(STOCK)}",
        )
    return StockResp(
        ok=True, sku=key, name=item["name"], stock=item["stock"],
        unit=item["unit"], price=item["price"], in_stock=item["stock"] > 0,
        message=(f"{item['name']} 现货 {item['stock']} {item['unit']}"
                 if item["stock"] > 0 else f"{item['name']} 暂时缺货，需预订"),
    )


@app.get("/api/order", response_model=OrderResp)
def get_order(order_id: str = Query(..., description="订单号，例如 SO2026001")):
    """查订单状态。"""
    key = order_id.strip().upper()
    o = ORDERS.get(key)
    if not o:
        raise HTTPException(
            status_code=404,
            detail=f"查不到订单 {order_id}。示例订单号：{', '.join(ORDERS)}",
        )
    return OrderResp(ok=True, order_id=key, **o)


@app.get("/")
def root():
    return {
        "name": "企业业务工具 API",
        "docs": "/docs",
        "endpoints": {
            "GET /api/health": "健康检查",
            "GET /api/stock?sku=X1-BASIC": "查库存",
            "GET /api/order?order_id=SO2026001": "查订单",
        },
    }


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8200)
    a = ap.parse_args()

    print("=" * 60)
    print("  企业业务工具 API")
    print("=" * 60)
    print(f"  地址: http://{a.host}:{a.port}")
    print(f"  文档: http://{a.host}:{a.port}/docs")
    print(f"  示例: http://{a.host}:{a.port}/api/stock?sku=X1-BASIC")
    print("=" * 60)
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
