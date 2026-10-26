# XAU Short stage-2 receiver: run the local sample notifications against a NEW, separate data folder under %TEMP%.
# It never touches the real data folder of config.json (nothing is deleted there).
$script = Join-Path $PSScriptRoot "xau_receiver.py"
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $exe = "py"; $pre = @("-3") } else { $exe = "python"; $pre = @() }
$env:PYTHONUTF8 = "1"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("xau_receiver_sample_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$cfgPath = Join-Path $tmp "config.sample-test.json"
@{ data_dir = (Join-Path $tmp "data") } | ConvertTo-Json | Set-Content -LiteralPath $cfgPath -Encoding UTF8
& $exe @pre $script ingest (Join-Path $PSScriptRoot "samples\normal_flow.jsonl") (Join-Path $PSScriptRoot "samples\bad_cases.jsonl") --config $cfgPath
& $exe @pre $script status --config $cfgPath
Write-Host ""
Write-Host "sample test data folder (separate from the real one): $tmp"
Write-Host "it can be deleted after checking: Remove-Item -LiteralPath '$tmp' -Recurse"
