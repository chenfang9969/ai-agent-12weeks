# =====================================================================
#  把 12 周计划仓库推到 GitHub
#  用法: 双击本文件，或者在终端里跑
#         powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DeepSeekHarness\12周计划\push-github.ps1"
#
#  说明:
#    - 脚本会问你两个东西: 仓库地址、GitHub 用户名
#    - 密码那一关请你粘贴 Personal Access Token (ghp_... 开头)
#    - 本文件必须保持 UTF-8 BOM, 否则 PowerShell 5.1 按 GBK 读会乱码
# =====================================================================

$ErrorActionPreference = 'Stop'
$root = 'D:\DeepSeekHarness\12周计划'

Write-Host ''
Write-Host '=====================================================================' -ForegroundColor Cyan
Write-Host '  推送 12 周计划仓库到 GitHub' -ForegroundColor Cyan
Write-Host '=====================================================================' -ForegroundColor Cyan
Write-Host ''

Set-Location $root

# ---------- 1. 检查是否已有 remote ----------
$existing = git remote get-url origin 2>$null
if ($existing) {
    Write-Host "[发现已有 remote] $existing" -ForegroundColor Yellow
    $ans = Read-Host '要替换成新的地址吗? (y/N)'
    if ($ans -match '^[Yy]') {
        git remote remove origin
    } else {
        Write-Host '[使用现有 remote 继续]' -ForegroundColor Green
    }
}

# ---------- 2. 问仓库地址 ----------
if (-not (git remote get-url origin 2>$null)) {
    Write-Host ''
    Write-Host '请粘贴你的 GitHub 仓库地址，形如:' -ForegroundColor White
    Write-Host '  https://github.com/你的用户名/ai-agent-12weeks.git' -ForegroundColor DarkGray
    $url = Read-Host '仓库地址'
    if (-not $url) { Write-Host '[取消] 没输入地址' -ForegroundColor Red; exit 1 }
    $url = $url.Trim()
    if ($url -notmatch '^https://') {
        Write-Host '[!] 建议用 https:// 开头的地址。' -ForegroundColor Yellow
    }
    git remote add origin $url
    Write-Host "[已设置 remote] $url" -ForegroundColor Green
}

# ---------- 3. 确认主分支名 ----------
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne 'main') {
    Write-Host "[当前分支] $branch -> 重命名为 main" -ForegroundColor Yellow
    git branch -M main
}

# ---------- 4. 推送前的最后检查 ----------
Write-Host ''
Write-Host '--- 推送前检查 ---' -ForegroundColor Cyan

# 4a. 有没有 .env 被跟踪
$envTracked = git ls-files '.env'
if ($envTracked) {
    Write-Host '[!! 危险] .env 已被 git 跟踪，里面可能有密钥!' -ForegroundColor Red
    Write-Host '    先处理它再推送。' -ForegroundColor Red
    exit 1
} else {
    Write-Host '[OK] .env 未被跟踪（密钥安全）' -ForegroundColor Green
}

# 4b. 有没有明显像密钥的东西被提交
$leak = git grep -I -n -E 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}' -- . 2>$null
if ($leak) {
    Write-Host '[!! 危险] 检测到疑似密钥内容:' -ForegroundColor Red
    $leak | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    exit 1
} else {
    Write-Host '[OK] 代码里没检测到 sk-/ghp_ 形式的密钥' -ForegroundColor Green
}

# 4c. 工作区是否干净
$dirty = git status --porcelain
if ($dirty) {
    Write-Host '[!] 还有未提交的改动，先提交:' -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    $ans = Read-Host '要现在用一条通用提交信息提交吗? (y/N)'
    if ($ans -match '^[Yy]') {
        git add -A
        git -c core.safecrlf=false commit -m 'W01: 收尾提交'
    } else {
        Write-Host '[中止] 请先手动提交' -ForegroundColor Red; exit 1
    }
} else {
    Write-Host '[OK] 工作区干净' -ForegroundColor Green
}

# ---------- 5. 推送 ----------
Write-Host ''
Write-Host '=====================================================================' -ForegroundColor Cyan
Write-Host '  开始推送' -ForegroundColor Cyan
Write-Host '  密码那一关请粘贴 Personal Access Token (ghp_... 开头)' -ForegroundColor Yellow
Write-Host '  Token 输入时不显示字符，这是正常的' -ForegroundColor DarkGray
Write-Host '=====================================================================' -ForegroundColor Cyan
Write-Host ''

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Host '=====================================================================' -ForegroundColor Green
    Write-Host '  推送成功!' -ForegroundColor Green
    Write-Host '=====================================================================' -ForegroundColor Green
    Write-Host ''
    Write-Host ("  仓库文件数: " + (git ls-files | Measure-Object -Line).Lines) -ForegroundColor Green
    Write-Host ("  提交次数  : " + (git log --oneline | Measure-Object -Line).Lines) -ForegroundColor Green
    Write-Host ("  远端地址  : " + (git remote get-url origin)) -ForegroundColor Green
    Write-Host ''
    Write-Host '  这就是 12 周计划要求的第 1 个资产: GitHub 项目' -ForegroundColor Cyan
} else {
    Write-Host ''
    Write-Host '[推送失败] 常见原因:' -ForegroundColor Red
    Write-Host '  1. Token 粘贴错了 -> 重新跑本脚本' -ForegroundColor White
    Write-Host '  2. 仓库地址写错了 -> 检查 https://github.com/用户名/仓库名.git' -ForegroundColor White
    Write-Host '  3. 远端已有内容(建仓库时勾了 README) -> 需要先 pull --rebase' -ForegroundColor White
    Write-Host '  4. Token 没勾 repo 权限' -ForegroundColor White
}

Write-Host ''
Read-Host '按回车关闭'
