# XAU Short stage-2 receiver: show recent receipts, states, intents and the log tail.
param([string]$Config = (Join-Path $PSScriptRoot "config.json"), [int]$Last = 30, [switch]$Follow)
$script = Join-Path $PSScriptRoot "xau_receiver.py"
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $exe = "py"; $pre = @("-3") } else { $exe = "python"; $pre = @() }
$env:PYTHONUTF8 = "1"
& $exe @pre $script show --last $Last --config $Config
& $exe @pre $script status --config $Config
$dataDir = Join-Path $PSScriptRoot "data"
if (Test-Path -LiteralPath $Config) {
    $cfgObj = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfgObj.data_dir) { $dataDir = if ([IO.Path]::IsPathRooted($cfgObj.data_dir)) { $cfgObj.data_dir } else { Join-Path (Split-Path -Parent (Resolve-Path -LiteralPath $Config).Path) $cfgObj.data_dir } }
}
$log = Join-Path $dataDir "receiver.log"
if (Test-Path -LiteralPath $log) { if ($Follow) { Get-Content -LiteralPath $log -Tail 20 -Wait } else { Get-Content -LiteralPath $log -Tail 20 } }
