$ErrorActionPreference = "Stop"
$taskName = "Market Brief - Daily Report"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Output "No '$taskName' task was found."
    exit 0
}
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Output "Removed '$taskName'."
