# XAU Short stage-2 receiver: show recent receipts, states and the log tail.
param([string]$Config = (Join-Path $PSScriptRoot "config.json"), [int]$Last = 30, [switch]$Follow)
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $exe = "py"; $pre = @("-3") } else { $exe = "python"; $pre = @() }
& $exe @pre (Join-Path $PSScriptRoot "xau_receiver.py") show --last $Last --config $Config
& $exe @pre (Join-Path $PSScriptRoot "xau_receiver.py") status --config $Config
$log = Join-Path $PSScriptRoot "data\receiver.log"
if (Test-Path $log) { if ($Follow) { Get-Content $log -Tail 20 -Wait } else { Get-Content $log -Tail 20 } }
