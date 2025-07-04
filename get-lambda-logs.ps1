#!/usr/bin/env pwsh
# PowerShell script to get Lambda CloudWatch logs

$LogGroupName = "/aws/lambda/aws-image-translate-image-processor"
$StartTime = [DateTimeOffset]::UtcNow.AddMinutes(-10).ToUnixTimeMilliseconds()

Write-Host "🔍 Getting recent logs from: $LogGroupName" -ForegroundColor Green
Write-Host "📅 Since: $((Get-Date).AddMinutes(-10).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Yellow

try {
    # Get recent log events
    $LogEvents = aws logs filter-log-events --log-group-name $LogGroupName --start-time $StartTime --output json | ConvertFrom-Json

    if ($LogEvents.events.Count -eq 0) {
        Write-Host "⚠️  No recent log events found" -ForegroundColor Yellow
    } else {
        Write-Host "📋 Found $($LogEvents.events.Count) recent log events:" -ForegroundColor Green
        Write-Host ""

        foreach ($event in $LogEvents.events | Sort-Object timestamp) {
            $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString('yyyy-MM-dd HH:mm:ss')
            Write-Host "[$timestamp] $($event.message)" -ForegroundColor White
        }
    }
} catch {
    Write-Host "❌ Error getting logs: $($_.Exception.Message)" -ForegroundColor Red
}
