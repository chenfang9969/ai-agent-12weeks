# Daily reminder launcher.
# NOTE: this file must stay saved as UTF-8 *with BOM*.
# Windows PowerShell 5.1 reads .ps1 as GBK when there is no BOM, which corrupts
# the Chinese path below and breaks parsing. Keep the BOM.

param([switch]$NoPause)

$ErrorActionPreference = 'SilentlyContinue'
$root = 'D:\DeepSeekHarness\12周计划'
$py = Join-Path $root 'reminder.py'

if (-not (Test-Path $py)) { exit 1 }

$host.UI.RawUI.WindowTitle = 'DSH 12-Week Plan Reminder'

python $py
Write-Host ''
Write-Host 'Window closes by itself. Press any key to close now.' -ForegroundColor DarkGray

# Auto-close after 60s so a scheduled run never leaves a dangling process.
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    if ($Host.UI.RawUI.KeyAvailable) { break }
    Start-Sleep -Milliseconds 500
}
exit 0
