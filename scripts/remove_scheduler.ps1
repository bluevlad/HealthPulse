# HealthPulse Windows Task Scheduler Removal Script
# Run this script as Administrator

$CrawlTaskName = "HealthPulse_DailyCrawl"
$SendTaskName = "HealthPulse_DailyNewsletter"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Removing HealthPulse scheduled tasks..." -ForegroundColor Yellow
Write-Host ""

# Remove Crawl Task
$crawlTask = Get-ScheduledTask -TaskName $CrawlTaskName -ErrorAction SilentlyContinue
if ($crawlTask) {
    Unregister-ScheduledTask -TaskName $CrawlTaskName -Confirm:$false
    Write-Host "  Removed: $CrawlTaskName" -ForegroundColor Green
} else {
    Write-Host "  Not found: $CrawlTaskName" -ForegroundColor Gray
}

# Remove Send Task
$sendTask = Get-ScheduledTask -TaskName $SendTaskName -ErrorAction SilentlyContinue
if ($sendTask) {
    Unregister-ScheduledTask -TaskName $SendTaskName -Confirm:$false
    Write-Host "  Removed: $SendTaskName" -ForegroundColor Green
} else {
    Write-Host "  Not found: $SendTaskName" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
