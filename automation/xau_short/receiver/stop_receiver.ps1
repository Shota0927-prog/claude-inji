# XAU Short stage-2 receiver: stop (reads the PID the receiver wrote to data\receiver.pid).
param([string]$DataDir = (Join-Path $PSScriptRoot "data"))
$pidFile = Join-Path $DataDir "receiver.pid"
if (-not (Test-Path $pidFile)) { Write-Host "no PID file ($pidFile): receiver not running?"; exit 0 }
$procId = [int](Get-Content $pidFile)
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
if ($proc) { Stop-Process -Id $procId; Write-Host "stopped PID $procId" } else { Write-Host "PID $procId not running" }
Remove-Item $pidFile -ErrorAction SilentlyContinue
