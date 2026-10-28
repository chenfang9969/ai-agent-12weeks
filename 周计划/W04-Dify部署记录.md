# W04 · Dify 本地部署记录

> 日期：2026-10-28
> 环境：Windows 11 + WSL 3.0.3 + Docker 29.9.2（D 盘）
> Dify 版本：1.18.0

---

## 一、部署位置

| 项 | 路径 |
|---|---|
| 代码 | `D:\Dify`（git clone，15123 文件）|
| compose 配置 | `D:\Dify\docker` |
| 环境变量 | `D:\Dify\docker\.env`（从 `.env.example` 复制）|
| Docker 数据 | `D:\DockerData` |
| 访问地址 | **http://localhost** |

---

## 二、启动命令

```powershell
# 每次要用 Dify 之前：
# 1. 确认 Docker Desktop 在运行（右下角鲸鱼图标）
# 2. 启动服务
cd D:\Dify\docker
docker compose up -d

# 停止（释放内存）
docker compose down

# 看状态
docker compose ps
```

---

## 三、装了哪些镜像（约 9.4 GB）

| 镜像 | 大小 |
|---|---|
| langgenius/dify-api | 3.98 GB |
| langgenius/dify-agent-backend | 1.54 GB |
| langgenius/dify-web | 911 MB |
| langgenius/dify-sandbox | 848 MB |
| langgenius/dify-agent-local-sandbox | 789 MB |
| postgres | 417 MB |
| cr.weaviate.io/weaviate | 302 MB |
| ubuntu/squid | 303 MB |
| nginx | 243 MB |
| redis | 41.7 MB |
| busybox | 6.8 MB |

**向量库只用了 weaviate**（默认），其余 qdrant/milvus/chroma 是可选 profile，没拉。

---

## 四、踩的坑（重要，以后重装直接用）

### 坑 1：`local_sandbox` 反复重启

**现象**：
```
docker-local_sandbox-1   Restarting (1)
```

**日志**：
```
shellctl: auth token is required: set SHELLCTL_AUTH_TOKEN or --token
```

**原因**：Dify 1.18 新增了 `dify-agent` 的本地沙箱，需要一个认证 token，
但 **`.env.example` 里没有这个变量**（官方文档未同步）。

**修复**：在 `D:\Dify\docker\.env` 末尾加两行（值必须相同）：

```
DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN=<随机 48 位十六进制>
DIFY_AGENT_SHELLCTL_AUTH_TOKEN=<同一个值>
```

生成随机值：
```powershell
$b = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
($b | ForEach-Object { $_.ToString("x2") }) -join ""
```

然后 `docker compose up -d` 重建。

### 坑 2：首次启动 web 能开但 API 502

**正常现象**。`api` 容器要先跑数据库迁移 + 起 gunicorn，约 **60-90 秒**。
等 `docker compose ps` 里 `docker-api-1` 变成 `(healthy)` 就好。

### 坑 3：Invoke-WebRequest 在非交互 shell 里报错

```
Windows PowerShell is in NonInteractive mode
```
用 `curl.exe` 代替（`-o NUL -w "%{http_code}"`）。

---

## 五、常用排障命令

```powershell
# 看所有容器状态
docker compose ps

# 看某个服务的日志
docker compose logs api --tail 50
docker compose logs local_sandbox --tail 30

# 测 API 是否就绪
curl.exe -s -o NUL -w "%{http_code}" http://localhost/console/api/setup

# 看资源占用
docker stats --no-stream
```

---

## 六、内存占用提醒

Dify 全家桶常驻内存约 **2-4 GB**（api + worker + weaviate + postgres + redis + nginx + sandbox）。
机器 16 GB 够用，但**别和其他重任务同时跑**。

不用时 `docker compose down` 释放。
