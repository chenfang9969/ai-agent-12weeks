# Desktop notification for the 12-week plan reminder.
# Must stay saved as UTF-8 *with BOM* (PowerShell 5.1 reads .ps1 as GBK without it).
#
# Input : env DSH_POPUP_TITLE, env DSH_POPUP_MSG
# Output: one of winrt-toast / burnttoast / balloon / beep  (last stdout line)
#
# Fallback chain, most reliable first:
#   1. WinRT native toast  - no module needed, works from Task Scheduler
#   2. BurntToast module   - only if already installed
#   3. WinForms balloon    - older but very compatible
#   4. console beep        - last resort

$ErrorActionPreference = 'SilentlyContinue'
$t = $env:DSH_POPUP_TITLE
$m = $env:DSH_POPUP_MSG
if (-not $t) { $t = '12-Week Plan' }
if (-not $m) { $m = 'Time to work.' }

function Show-WinRTToast {
    try {
        [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    } catch { return $false }

    # A toast needs a registered AppUserModelID. Probe a few known-good ones.
    $ids = @()
    $shortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Windows PowerShell\Windows PowerShell.lnk'
    if (Test-Path $shortcut) {
        $ids += '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    }
    $ids += 'Microsoft.Windows.Explorer'

    $body = '<toast><visual><binding template="ToastGeneric"><text>TITLE</text><text>MSG</text></binding></visual></toast>'
    $xmlText = $body.Replace('TITLE', [System.Security.SecurityElement]::Escape($t)).Replace('MSG', [System.Security.SecurityElement]::Escape($m))

    foreach ($id in $ids) {
        try {
            $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
            $doc.LoadXml($xmlText)
            $toast = New-Object Windows.UI.Notifications.ToastNotification $doc
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show($toast)
            return $true
        } catch { continue }
    }
    return $false
}

function Show-BurntToast {
    Import-Module BurntToast -ErrorAction SilentlyContinue
    if (-not (Get-Module BurntToast)) { return $false }
    try {
        New-BurntToastNotification -Text $t, $m | Out-Null
        return $true
    } catch { return $false }
}

function Show-Balloon {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.Visible = $true
        $ni.ShowBalloonTip(20000, $t, $m, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 8
        $ni.Dispose()
        return $true
    } catch { return $false }
}

if (Show-WinRTToast)      { Write-Output 'winrt-toast'; exit 0 }
if (Show-BurntToast)      { Write-Output 'burnttoast';  exit 0 }
if (Show-Balloon)         { Write-Output 'balloon';     exit 0 }
[console]::beep(880, 300)
[console]::beep(660, 300)
Write-Output 'beep'
exit 0
