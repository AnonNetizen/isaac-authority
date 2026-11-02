param(
    [string]$Game = '<GAME>',
    [string]$ProcessId = '<PID>',
    [ValidateSet('print','offline','build','state-probe','skip-packet','guest-render','dual-machine')][string]$Step = 'print',
    [string]$Report
)
$ErrorActionPreference = 'Stop'
# Prints the owner commands. It does not mark the prototype playable.
# --check-report is a schema check of a JSON file the owner already captured.
$taskScript = Join-Path $PSScriptRoot 'live_acceptance.py'
if ($Report) {
    py -3 $taskScript --check-report $Report
    exit $LASTEXITCODE
}
if ($Step -eq 'print') {
    py -3 $taskScript --print --game $Game --pid $ProcessId
} else {
    py -3 $taskScript --step $Step --game $Game --pid $ProcessId
}
exit $LASTEXITCODE
