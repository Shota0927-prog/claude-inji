# XAU Short stage-2 receiver: stop. Checks that the PID in receiver.pid is really this receiver before stopping it
# (command line contains xau_receiver.py and serve, and the process start time matches the recorded start time),
# so a re-used PID of another program is never stopped.
param([string]$Config = (Join-Path $PSScriptRoot "config.json"))
$ErrorActionPreference = "Stop"
$dataDir = Join-Path $PSScriptRoot "data"
if (Test-Path -LiteralPath $Config) {
    $cfgObj = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfgObj.data_dir) {
        $dataDir = if ([IO.Path]::IsPathRooted($cfgObj.data_dir)) { $cfgObj.data_dir } else { Join-Path (Split-Path -Parent (Resolve-Path -LiteralPath $Config).Path) $cfgObj.data_dir }
    }
}
$pidFile = Join-Path $dataDir "receiver.pid"
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host "no PID file ($pidFile): receiver not running?"; exit 0 }
$info = Get-Content -LiteralPath $pidFile -Raw -Encoding UTF8 | ConvertFrom-Json
$procId = [int]$info.pid
$proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
if (-not $proc) { Write-Host "PID $procId is not running; removing the stale PID file"; Remove-Item -LiteralPath $pidFile; exit 0 }
$cmd = [string]$proc.CommandLine
$okCmd = $cmd.Contains("xau_receiver.py") -and $cmd.Contains("serve")
$started = [datetimeoffset]::Parse([string]$info.started_utc).UtcDateTime
$created = ([datetime]$proc.CreationDate).ToUniversalTime()
$okTime = [math]::Abs(($created - $started).TotalSeconds) -le 120
if (-not ($okCmd -and $okTime)) {
    Write-Error "PID $procId does not look like this receiver (command line / start time mismatch). Not stopping it. Check manually."
    exit 1
}
Stop-Process -Id $procId
Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
Write-Host "stopped receiver PID $procId"
