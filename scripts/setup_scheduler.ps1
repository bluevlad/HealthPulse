# HealthPulse Windows Task Scheduler Setup Script
# Run this script as Administrator

$TaskName = "HealthPulse_DailyNewsletter"
$TaskDescription = "HealthPulse Daily Healthcare News Collection and Email Delivery"
$ScriptPath = "C:\GIT\HealthPulse\scripts\run_daily.bat"
$WorkingDir = "C:\GIT\HealthPulse"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# Remove existing task if exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create trigger (Daily at 7:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM

# Create action
$Action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory $WorkingDir

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -WakeToRun

# Create principal (run whether user is logged on or not)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $TaskDescription `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Principal $Principal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Task Scheduler Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task Name: $TaskName" -ForegroundColor Cyan
Write-Host "Schedule: Daily at 7:00 AM" -ForegroundColor Cyan
Write-Host "Script: $ScriptPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "To verify, open Task Scheduler and look for '$TaskName'" -ForegroundColor Yellow
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  - Run now: schtasks /run /tn `"$TaskName`"" -ForegroundColor White
Write-Host "  - Disable: schtasks /change /tn `"$TaskName`" /disable" -ForegroundColor White
Write-Host "  - Enable:  schtasks /change /tn `"$TaskName`" /enable" -ForegroundColor White
Write-Host "  - Delete:  schtasks /delete /tn `"$TaskName`" /f" -ForegroundColor White
