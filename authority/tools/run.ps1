param(
    [Parameter(Mandatory=$true)][string]$Game,
    [ValidateSet('check','steam-probe','attach','steam-launch','stop')][string]$Mode = 'check',
    [uint32]$ProcessId = 0,
    [string]$OutputDirectory,
    [ValidateSet('capture','preview')][string]$Role = 'capture',
    [string]$BinaryDirectory,
    [string]$Peer,
    [string]$Session,
    [string]$Manifest,
    [switch]$ObjectProbe,
    [switch]$LayoutProbe,
    [switch]$CallProbe,
    [string]$CandidateRva,
    [uint32]$ProbeMs = 10000,
    [uint32]$WaitMs = 600000,
    [switch]$StateProbe,
    [switch]$CaptureState,
    [switch]$CapturePacket,
    [switch]$SkipProbe,
    [string]$SkipCycles = '2000,5000,2000',
    [uint32]$SkipRet = 0,
    [switch]$RuntimeProbe,
    [string]$RuntimeSuite,
    [switch]$ApiProbe
)
$ErrorActionPreference = 'Stop'
$taskRoot = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'bin\isaac-authority.exe')) {
    $PSScriptRoot
} else { Split-Path -Parent $PSScriptRoot }
if (-not $BinaryDirectory) {
    $BinaryDirectory = Join-Path $taskRoot 'bin'
    if (-not (Test-Path -LiteralPath (Join-Path $BinaryDirectory 'isaac-authority.exe'))) {
        foreach($taskCandidate in @((Join-Path (Split-Path -Parent $taskRoot) 'bin'),
            (Join-Path $taskRoot 'build-suite-final\Release'),(Join-Path $taskRoot 'build-suite-shared-release\Release'),(Join-Path $taskRoot 'build-suite-release\Release'),(Join-Path $taskRoot 'build-personal-release\Release'),(Join-Path $taskRoot 'build-packed-final\Release'),(Join-Path $taskRoot 'build-assets-release\Release'),(Join-Path $taskRoot 'build-assets-final\Release'),(Join-Path $taskRoot 'build-assets\Release'),(Join-Path $taskRoot 'build-api\Release'),(Join-Path $taskRoot 'build-runtime\Release'),(Join-Path $taskRoot 'build-bridge\Release'),(Join-Path $taskRoot 'build-release\Release'),(Join-Path $taskRoot 'build\Release'))) {
            if(Test-Path -LiteralPath (Join-Path $taskCandidate 'isaac-authority.exe')) { $BinaryDirectory=$taskCandidate;break }
        }
    }
}
$taskLauncher = Join-Path $BinaryDirectory 'isaac-authority.exe'
if (-not (Test-Path -LiteralPath $taskLauncher)) { throw 'Build the research binaries or select -BinaryDirectory.' }
if ($Mode -eq 'stop' -and -not $OutputDirectory) { throw 'Stop requires the exact -OutputDirectory of the observer.' }
if ($Mode -eq 'attach' -and -not $ProcessId) { throw 'Attach requires the game -ProcessId.' }
if ($ObjectProbe -and $Mode -notin @('attach','steam-launch')) { throw 'Object probe requires attach or steam-launch.' }
if ($LayoutProbe -and $Mode -notin @('attach','steam-launch')) { throw 'Layout probe requires attach or steam-launch.' }
if ($CallProbe -and $Mode -notin @('attach','steam-launch')) { throw 'Call probe requires attach or steam-launch.' }
if ($StateProbe -and $Mode -notin @('attach','steam-launch')) { throw 'State probe requires attach or steam-launch.' }
if ($CaptureState -and -not $CallProbe) { throw 'Capture state requires -CallProbe.' }
if ($CapturePacket -and -not $CallProbe) { throw 'Capture packet requires -CallProbe.' }
if ($SkipProbe -and $Mode -notin @('attach','steam-launch')) { throw 'Skip probe requires attach or steam-launch.' }
if ($SkipProbe -and -not $CandidateRva) { throw 'Skip probe requires -CandidateRva.' }
if ($CallProbe -and -not $CandidateRva) { throw 'Call probe requires -CandidateRva.' }
if (@($ObjectProbe, $LayoutProbe, $CallProbe, $StateProbe, $SkipProbe, $RuntimeProbe, $ApiProbe | Where-Object { $_ }).Count -gt 1) { throw 'Choose one diagnostic.' }
if ($RuntimeProbe -and $Mode -notin @('attach','steam-launch')) { throw 'Runtime probe requires attach or steam-launch.' }
if ($RuntimeSuite) {$RuntimeProbe=$true;if($Mode -notin @('attach','steam-launch')) {throw 'Runtime suite requires attach or steam-launch.'}}
if ($RuntimeProbe -and $ObjectProbe) { throw 'Choose runtime or object probe.' }
if ($ApiProbe -and $Mode -notin @('attach','steam-launch')) { throw 'API probe requires attach or steam-launch.' }
if ($ApiProbe -and ($ObjectProbe -or $RuntimeProbe)) { throw 'Choose one diagnostic.' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $taskRoot ('runs\' + [guid]::NewGuid().ToString('N')) }
$taskArguments = @('--game', $Game, '--out', $OutputDirectory)
if ($Mode -eq 'attach') { $taskArguments += @('--attach', [string]$ProcessId) }
else { $taskArguments += @('--' + $Mode) }
if ($Mode -eq 'attach' -or $Mode -eq 'steam-launch') {
    if ($CallProbe) {
        if ($Peer -or $Role -ne 'capture') { throw 'Call probe cannot combine peer/preview observation.' }
        $taskArguments += @('--call-probe', '--candidate-rva', $CandidateRva, '--probe-ms', [string]$ProbeMs, '--wait-ms', [string]$WaitMs)
        if ($CaptureState) { $taskArguments += '--capture-state' }
        if ($CapturePacket) { $taskArguments += '--capture-packet' }
    } elseif ($SkipProbe) {
        if ($Peer -or $Role -ne 'capture') { throw 'Skip probe cannot combine peer/preview observation.' }
        $taskArguments += @('--skip-probe', '--candidate-rva', $CandidateRva, '--skip-cycles', $SkipCycles, '--skip-ret', [string]$SkipRet)
    } elseif ($StateProbe) {
        if ($Peer -or $Role -ne 'capture') { throw 'State probe cannot combine peer/preview observation.' }
        $taskArguments += '--state-probe'
    } elseif ($LayoutProbe) {
        if ($Peer -or $Role -ne 'capture') { throw 'Layout probe cannot combine peer/preview observation.' }
        $taskArguments += '--layout-probe'
    } elseif ($ApiProbe) {
        if($Peer -or $Role -ne 'capture') { throw 'API probe cannot combine peer/preview observation.' }
        $taskArguments += '--api-probe'
    } elseif ($RuntimeProbe) {
        if($Peer -or $Role -ne 'capture') { throw 'Runtime probe cannot combine peer/preview observation.' }
        $taskSource = if(Test-Path -LiteralPath (Join-Path $taskRoot 'source\research\native_context.lua')) { Join-Path $taskRoot 'source' } else { $taskRoot }
        $taskArguments += @('--runtime-probe','--runtime-source',$taskSource)
        if($RuntimeSuite) {$taskArguments += @('--runtime-suite',[IO.Path]::GetFullPath($RuntimeSuite))}
    } elseif ($ObjectProbe) {
        if($Peer -or $Role -ne 'capture') { throw 'Object probe cannot combine peer/preview observation.' }
        $taskArguments += '--object-probe'
    } else { $taskArguments += @('--role', $Role) }
    if ($Peer) {
        if (-not $Session -or -not $Manifest) { throw 'Peer observation requires -Session and -Manifest.' }
        $taskArguments += @('--peer', $Peer, '--session', $Session, '--manifest', $Manifest)
    }
}
& $taskLauncher @taskArguments
if ($LASTEXITCODE -ne 0) { throw "Research launcher failed ($LASTEXITCODE)." }
if ($Mode -eq 'attach' -or $Mode -eq 'steam-launch') { Write-Output ('Run directory: ' + $OutputDirectory) }
