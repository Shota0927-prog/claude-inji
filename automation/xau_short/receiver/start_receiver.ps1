# XAU Short stage-2 receiver: start in the background (NO ORDERS; records notifications only).
# Usage:  powershell -ExecutionPolicy Bypass -File .\start_receiver.ps1 [-Config .\config.json]
# Paths with spaces / Japanese characters are passed as one quoted argument each (Windows command-line quoting rules).
param([string]$Config = (Join-Path $PSScriptRoot "config.json"))
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Config)) { Write-Error "config not found: $Config (copy config.example.json to config.json first)"; exit 1 }
$Config = (Resolve-Path -LiteralPath $Config).Path
if (-not $env:XAU_RECEIVER_TOKEN) {
    Write-Error "environment variable XAU_RECEIVER_TOKEN is not set (see README_ja.md). The receiver refuses to start without it."
    exit 1
}
function Format-WinArg([string]$a) {
    # CommandLineToArgvW rules: double the backslashes before a quote and at the end, escape the quote, wrap in quotes
    $s = $a -replace '(\\*)"', '$1$1\"'
    $s = $s -replace '(\\+)$', '$1$1'
    return '"' + $s + '"'
}
$script = Join-Path $PSScriptRoot "xau_receiver.py"
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $exe = "py"; $pre = @("-3") } else { $exe = "python"; $pre = @() }
$argLine = (@($pre) + @($script, "serve", "--config", $Config) | ForEach-Object { Format-WinArg $_ }) -join " "
$env:PYTHONUTF8 = "1"
$p = Start-Process -FilePath $exe -ArgumentList $argLine -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { Write-Error "receiver exited (code $($p.ExitCode)); check the receiver.log in the data folder"; exit 1 }
$cfgObj = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
$port = if ($cfgObj.port) { $cfgObj.port } else { 8787 }
Write-Host "receiver started (launcher PID $($p.Id)). Health check: Invoke-RestMethod http://127.0.0.1:$port/health"
