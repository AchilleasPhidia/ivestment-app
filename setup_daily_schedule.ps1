$ErrorActionPreference = "Stop"

$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
$scriptPath = Join-Path $projectPath "daily_report.py"
$taskName = "Market Brief - Daily Report"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project virtual environment not found. Run the README setup commands before creating the scheduled task."
}

$arguments = "-u `"$scriptPath`" --region us"
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $projectPath
$runAt = Get-Date -Hour 22 -Minute 15 -Second 0
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $runAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Creates a weekday Yahoo Finance Market Brief archive report." `
    -Force | Out-Null

Write-Output "Created '$taskName'. It runs weekdays at 10:15 PM local time when this user is logged in and the computer is available."
