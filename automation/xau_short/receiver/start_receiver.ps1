# XAU Short stage-2 receiver: start in the background (NO ORDERS; records notifications only).
# Usage:  powershell -ExecutionPolicy Bypass -File .\start_receiver.ps1 [-Config .\config.json]
param([string]$Config = (Join-Path $PSScriptRoot "config.json"))
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Config)) { Write-Error "config not found: $Config (copy config.example.json to config.json first)"; exit 1 }
if (-not $env:XAU_RECEIVER_TOKEN) {
    Write-Error "environment variable XAU_RECEIVER_TOKEN is not set (see README_ja.md). The receiver refuses to start without it."
    exit 1
}
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $exe = "py"; $pre = @("-3") } else { $exe = "python"; $pre = @() }
$argList = $pre + @((Join-Path $PSScriptRoot "xau_receiver.py"), "serve", "--config", $Config)
$p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
if ($p.HasExited) { Write-Error "receiver exited (code $($p.ExitCode)); check data\receiver.log"; exit 1 }
Write-Host "receiver started (launcher PID $($p.Id)). Health check: Invoke-RestMethod http://127.0.0.1:8787/health"
