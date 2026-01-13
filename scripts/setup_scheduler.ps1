# HealthPulse Windows Task Scheduler Setup Script
# Run this script as Administrator
#
# Schedule:
#   - Crawling: Daily at 7:00 AM (news collection + AI analysis)
#   - Newsletter: Daily at 8:00 AM (email delivery)

$CrawlTaskName = "HealthPulse_DailyCrawl"
$SendTaskName = "HealthPulse_DailyNewsletter"
$WorkingDir = "C:\GIT\HealthPulse"
$CrawlScriptPath = "C:\GIT\HealthPulse\scripts\run_crawl.bat"
$SendScriptPath = "C:\GIT\HealthPulse\scripts\run_send.bat"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# ==========================================
# Remove existing tasks if exists
# ==========================================
$existingCrawlTask = Get-ScheduledTask -TaskName $CrawlTaskName -ErrorAction SilentlyContinue
if ($existingCrawlTask) {
    Write-Host "Removing existing crawl task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $CrawlTaskName -Confirm:$false
}

$existingSendTask = Get-ScheduledTask -TaskName $SendTaskName -ErrorAction SilentlyContinue
if ($existingSendTask) {
    Write-Host "Removing existing send task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $SendTaskName -Confirm:$false
}

# ==========================================
# Create Crawling Task (7:00 AM)
# ==========================================
Write-Host ""
Write-Host "Creating Crawl Task..." -ForegroundColor Cyan

$CrawlTrigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$CrawlAction = New-ScheduledTaskAction -Execute $CrawlScriptPath -WorkingDirectory $WorkingDir
$CrawlSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -WakeToRun
$CrawlPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

Register-ScheduledTask `
    -TaskName $CrawlTaskName `
    -Description "HealthPulse Daily News Crawling and AI Analysis (7:00 AM)" `
    -Trigger $CrawlTrigger `
    -Action $CrawlAction `
    -Settings $CrawlSettings `
    -Principal $CrawlPrincipal

Write-Host "  Crawl task created: $CrawlTaskName" -ForegroundColor Green

# ==========================================
# Create Newsletter Send Task (8:00 AM)
# ==========================================
Write-Host ""
Write-Host "Creating Send Task..." -ForegroundColor Cyan

$SendTrigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
$SendAction = New-ScheduledTaskAction -Execute $SendScriptPath -WorkingDirectory $WorkingDir
$SendSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -WakeToRun
$SendPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

Register-ScheduledTask `
    -TaskName $SendTaskName `
    -Description "HealthPulse Daily Newsletter Delivery (8:00 AM)" `
    -Trigger $SendTrigger `
    -Action $SendAction `
    -Settings $SendSettings `
    -Principal $SendPrincipal

Write-Host "  Send task created: $SendTaskName" -ForegroundColor Green

# ==========================================
# Summary
# ==========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Task Scheduler Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Tasks Created:" -ForegroundColor Cyan
Write-Host "  1. $CrawlTaskName - Daily at 7:00 AM" -ForegroundColor White
Write-Host "     (News collection + AI analysis)" -ForegroundColor Gray
Write-Host "  2. $SendTaskName - Daily at 8:00 AM" -ForegroundColor White
Write-Host "     (Newsletter email delivery)" -ForegroundColor Gray
Write-Host ""
Write-Host "To verify, open Task Scheduler and look for 'HealthPulse_*'" -ForegroundColor Yellow
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  - Run crawl now:  schtasks /run /tn `"$CrawlTaskName`"" -ForegroundColor White
Write-Host "  - Run send now:   schtasks /run /tn `"$SendTaskName`"" -ForegroundColor White
Write-Host "  - Disable crawl:  schtasks /change /tn `"$CrawlTaskName`" /disable" -ForegroundColor White
Write-Host "  - Disable send:   schtasks /change /tn `"$SendTaskName`" /disable" -ForegroundColor White
Write-Host "  - Delete all:     .\remove_scheduler.ps1" -ForegroundColor White
Write-Host ""
