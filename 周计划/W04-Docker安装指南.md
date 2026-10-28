# W04 · 把 Docker 装到 D 盘（明天照着做）

> 目标：**Docker 程序 + WSL2 + 镜像数据全部落在 D 盘**，C 盘只占最小。
> 预计 40-60 分钟（含下载），**中间可能要重启一次**。
>
> 你的机器：C 盘剩 38 GB / D 盘剩 79.5 GB / 16 GB 内存 / 虚拟化已开启 ✅

---

## 第 1 步 · 装 WSL2（管理员 PowerShell）

**必须以管理员身份打开 PowerShell**（开始菜单搜 PowerShell → 右键 → 以管理员身份运行）

```powershell
wsl --install
```

**这一步会**：启用 WSL 功能 + 装 WSL2 内核 + 装 Ubuntu

**✅ 检查点**：命令跑完会提示**重启电脑**。

**⚠️ 如果卡在下载**：可能是网络问题，重跑一次 `wsl --install`。

---

## 第 2 步 · 重启后验证 WSL

```powershell
wsl --status
wsl -l -v
```

**✅ 检查点**：`wsl -l -v` 应该看到 `Ubuntu`，且 `VERSION` 列是 **2**。

**⚠️ 如果 VERSION 是 1**：
```powershell
wsl --set-default-version 2
```

---

## 第 3 步 · 把 WSL 的 Ubuntu 搬到 D 盘（可选但推荐）

> 如果第 2 步看到 Ubuntu 已经在 C 盘且你不在意多占几个 G，这步可以跳过。
> **但 Docker 的镜像数据一定要搬（第 5 步）。**

```powershell
# 导出
wsl --export Ubuntu D:\wsl-ubuntu.tar

# 注销原来的（会删除 C 盘上那份）
wsl --unregister Ubuntu

# 导入到 D 盘
mkdir D:\WSL\Ubuntu
wsl --import Ubuntu D:\WSL\Ubuntu D:\wsl-ubuntu.tar --version 2

# 删掉临时 tar（几个 G）
Remove-Item D:\wsl-ubuntu.tar
```

**✅ 检查点**：`wsl -l -v` 能看到 Ubuntu，且可以 `wsl -d Ubuntu echo ok` 正常输出。

---

## 第 4 步 · 装 Docker Desktop 到 D 盘

1. 下载：https://www.docker.com/products/docker-desktop/
2. **安装时选 "Install for all users"** 或自定义
3. 如果想用命令行指定目录：

```powershell
cd $env:USERPROFILE\Downloads
Start-Process ".\Docker Desktop Installer.exe" -ArgumentList `
  "install", "--installation-dir=D:\Docker", "--wsl-default-data-root=D:\DockerData" -Wait
```

> `--wsl-default-data-root` 这个参数**很关键**——它决定 docker 的 VHDX 存在哪。

**✅ 检查点**：开始菜单里出现 Docker Desktop。

---

## 第 5 步 · 把镜像数据改到 D 盘（最重要）

打开 Docker Desktop → 右上角 **齿轮 Settings** → **Resources** → **Advanced**

找到 **Disk image location**，改成：

```
D:\DockerData
```

点 **Apply & restart**。

**✅ 检查点**：改完后这个路径显示 `D:\DockerData`。

**⚠️ 如果找不到这个设置**：说明 Docker Desktop 版本较新，可能在 **Settings → Resources → Advanced → Disk usage** 里。

---

## 第 6 步 · 验证 Docker 能用

```powershell
docker --version
docker run hello-world
```

**✅ 检查点**：看到 `Hello from Docker!` 这行字。

**⚠️ 如果报 "cannot connect to the Docker daemon"**：Docker Desktop 还没启动，等右下角鲸鱼图标变绿。

---

## 第 7 步 · 验证数据确实在 D 盘

```powershell
# 看 docker 的数据盘在哪
docker info --format '{{.DockerRootDir}}'
```

**✅ 检查点**：输出里应该出现 `D:\DockerData`（或 D 盘路径）。

**再确认 C 盘没被偷吃**：
```powershell
# 跑完 hello-world 之后，对比前后 C 盘剩余
(Get-PSDrive C).Free / 1GB
```

---

## 装完之后

**回来告诉我三件事**：

1. `docker run hello-world` 成功了吗？
2. `docker info --format '{{.DockerRootDir}}'` 输出是什么？
3. C 盘剩余空间变了吗？

**然后我们进 Dify 部署。**

---

## 常见失败与处理

| 症状 | 原因 | 处理 |
|---|---|---|
| `wsl --install` 报 "无权限" | 不是管理员 | 右键"以管理员身份运行" |
| WSL 装完但 `wsl -l -v` 是空的 | 没装发行版 | `wsl --install -d Ubuntu` |
| Docker 启动报 "WSL 2 installation is incomplete" | WSL2 内核没装 | 下载 https://aka.ms/wsl2kernel 安装 |
| `docker run` 卡在 pulling | 网络/镜像源慢 | 配镜像加速器（明天我给） |
| 安装要重启两次 | 正常 | 重启完再继续 |

---

## 磁盘预算（心里有数）

| 项目 | 大小 |
|---|---|
| WSL2 + Ubuntu | 约 1-2 GB |
| Docker Desktop 本体 | 约 2 GB |
| Dify 全套镜像（后面要拉）| **约 8-15 GB** |
| 运行中的容器数据 | 2-4 GB |
| **合计** | **约 15-20 GB** |

**D 盘 79.5 GB 够用。**

---

## 实测记录（2026-10-28 完成）

| 项 | 结果 |
|---|---|
| WSL | 3.0.3，内核 6.18.54.1 |
| Docker | 29.9.2 |
| 程序位置 | `D:\Docker` |
| 数据位置 | `D:\DockerData`（1.54 GB）|
| C 盘 Docker 数据 | 无（没偷占）|
| `docker run hello-world` | ✅ 成功 |

### 踩的坑（重要）

**1. 代理会拦微软下载**
`
wsl --install  →  "服务器返回无效或不可识别的响应" / "无法与服务器建立连接"
`
解法：**代理切全局 + 加 `--web-download`（走 GitHub 通道）+ 日本节点**，一次下好。

**2. 不需要装 Ubuntu**
Docker Desktop 自带 `docker-desktop` WSL 发行版，不用 Ubuntu。省 500 MB 下载。

**3. GUI 配置界面怎么选**
- ✅ Per-user installation
- ✅ WSL 2
- ❌ 不要选 Docker VMM (Beta)

**4. 装完老窗口读不到 docker 命令**
新开窗口即可；或在当前窗口刷新：
```powershell
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
```
