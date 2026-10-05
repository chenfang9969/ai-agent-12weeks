# Register Windows scheduled tasks: 20:00 tech block, 22:30 daily log.
# ASCII-only on purpose (PowerShell 5.1 reads .ps1 as GBK).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DeepSeekHarness\12周计划\setup-reminders.ps1"
#   powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DeepSeekHarness\12周计划\setup-reminders.ps1" -Remove
#   powershell -NoProfile -ExecutionPolicy Bypass -File "D:\DeepSeekHarness\12周计划\setup-reminders.ps1" -Test

param([switch]$Remove, [switch]$Test)

$ErrorActionPreference = 'Stop'
$root = 'D:\DeepSeekHarness\12周计划'
$launcher = Join-Path $root 'remind.ps1'

if ($Remove) {
    $found = Get-ScheduledTask -TaskName 'DSH-*' -ErrorAction SilentlyContinue
    if (-not $found) { Write-Host '[info] no DSH scheduled task found'; exit 0 }
    foreach ($t in $found) {
        Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false
        Write-Host ("[removed] " + $t.TaskName) -ForegroundColor Yellow
    }
    exit 0
}

if ($Test) {
    powershell -NoProfile -ExecutionPolicy Bypass -File $launcher
    exit 0
}

if (-not (Test-Path $launcher)) { throw "launcher not found: $launcher" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $launcher)

# 20:00 = start the tech block. 22:30 = write the daily log.
$defs = @(
    @{ Name = 'DSH-12Week-TechBlock'; Time = '20:00'; Desc = 'Golden 1 hour: work on today task card' },
    @{ Name = 'DSH-12Week-DailyLog';  Time = '22:30'; Desc = '30 min log: what you learned / what you built' }
)

$user = "$env:USERDOMAIN\$env:USERNAME"
$endDate = [datetime]'2026-12-28T23:59:00'   # plan ends 2026-12-28; tasks self-expire

foreach ($d in $defs) {
    $trigger = New-ScheduledTaskTrigger -Daily -At $d.Time
    $trigger.EndBoundary = $endDate.ToString('s')   # stop after the 12-week plan ends
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $d.Name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description $d.Desc -Force | Out-Null

    Write-Host ("[OK] {0}  ->  daily {1}  (until 2026-12-28)" -f $d.Name, $d.Time) -ForegroundColor Green
}

Write-Host ''
Get-ScheduledTask -TaskName 'DSH-12Week-*' |
    Select-Object TaskName, State, @{n = 'NextRun'; e = { ($_ | Get-ScheduledTaskInfo).NextRunTime } } |
    Format-Table -AutoSize

Write-Host 'Test now : powershell -File setup-reminders.ps1 -Test' -ForegroundColor Cyan
Write-Host 'Remove   : powershell -File setup-reminders.ps1 -Remove' -ForegroundColor DarkGray
