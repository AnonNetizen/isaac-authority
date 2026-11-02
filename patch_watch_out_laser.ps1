param(
    [ValidateSet('status', 'install', 'restore', 'verify', 'diagnose')]
    [string]$Action = 'status',
    [string]$ModDir,
    [switch]$AllowUnreviewed,
    [string]$SaveDir
)

$ErrorActionPreference = 'Stop'

$taskVersion = 2
$taskToolVersion = '2.0.0'
$taskWorkshopId = '2887926286'
$taskOriginalHash = '8651d5155e9223f800fe78332e16dbf50b452ab417a1d1080a5bcb3c8e69a25b'
$taskBackupName = 'main.lua.isaac-stability-v1.backup'
$taskManifestName = 'isaac-stability.json'
$taskLegacyManifestName = 'isaac-stability-v1.json'
$taskMarkerV1 = 'ISAAC_COOP_STABILITY_V1_BEGIN'
$taskMarkerV1End = 'ISAAC_COOP_STABILITY_V1_END'
$taskMarkerV2 = 'ISAAC_COOP_STABILITY_V2_BEGIN'
$taskMarkerV2End = 'ISAAC_COOP_STABILITY_V2_END'
$taskRenderAnchor = 'function postRender(self)'
$taskStartAnchor = '    local function postGameStarted(self)'
$taskPostUpdateRegistration = 'mod:AddCallback(ModCallback.POST_UPDATE, postRender)'
$taskPostStartedRegistration = 'mod:AddCallback(ModCallback.POST_GAME_STARTED, postGameStarted)'
$taskDispatchers = @('IHateDelirium', 'VanillaElseIfHell', 'RevCompatibility')
$taskFingerprintLength = 12
$taskHealthy = @('original_supported', 'patched_verified', 'patched_v1_verified')
$taskInstallNote = 'Both players must install the same patch and start a NEW run. Run verify on both machines and compare PATCH FINGERPRINT.'
$taskRestoreNote = 'Original mod file restored; the backup is kept in the mod directory.'
$taskVerifyNote = 'Both players must show the same PATCH FINGERPRINT before starting a new run.'
$taskScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskUtf8 = New-Object System.Text.UTF8Encoding($false)
$taskKnownSources = @{}
$taskKnownSources[$taskOriginalHash] = @{ mod_version = '1.1'; label = 'workshop 1.1' }

function Get-TaskHash([byte[]]$Data) {
    $taskHasher = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($taskHasher.ComputeHash($Data))).Replace('-', '').ToLowerInvariant() }
    finally { $taskHasher.Dispose() }
}

function Get-TaskFingerprint([string]$Digest) {
    return $Digest.Substring(0, $taskFingerprintLength).ToUpperInvariant()
}

function Get-TaskNewline([string]$Text) {
    if ($Text.Contains("`r`n")) { return "`r`n" }
    return "`n"
}

function Get-TaskPayload([string]$Nl) {
    $text = [IO.File]::ReadAllText((Join-Path $taskScriptRoot 'coop_guard.lua'), $taskUtf8)
    $text = $text.Replace("`r`n", "`n").TrimEnd([char[]]"`r`n")
    return ($text.Replace("`n", $Nl) + $Nl)
}

function Get-TaskStructure([string]$Text) {
    $normalized = $Text.Replace("`r`n", "`n")
    $lines = $normalized.Split("`n")
    $problems = New-Object 'System.Collections.Generic.List[string]'
    $spawnFunctions = New-Object 'System.Collections.Generic.List[string]'
    $callLines = New-Object 'System.Collections.Generic.List[int]'
    $postRenderLines = 0

    if ($Text.Contains($taskMarkerV1) -or $Text.Contains($taskMarkerV2)) {
        $problems.Add('file already contains a stability patch marker')
    }

    $render = @()
    $started = @()
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -ceq $taskRenderAnchor) { $render += $i }
        if ($lines[$i] -ceq $taskStartAnchor) { $started += $i }
    }
    if ($render.Count -ne 1) { $problems.Add("expected exactly one '$taskRenderAnchor' line, found $($render.Count)") }
    if ($started.Count -ne 1) { $problems.Add("expected exactly one postGameStarted anchor, found $($started.Count)") }

    $updateCalls = 0
    $startedCalls = 0
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -ceq $taskPostUpdateRegistration -and -not $trimmed.StartsWith('--')) { $updateCalls++ }
        if ($trimmed -ceq $taskPostStartedRegistration -and -not $trimmed.StartsWith('--')) { $startedCalls++ }
    }
    if ($updateCalls -ne 1) { $problems.Add("expected exactly one POST_UPDATE postRender registration, found $updateCalls") }
    if ($startedCalls -ne 1) { $problems.Add("expected exactly one POST_GAME_STARTED postGameStarted registration, found $startedCalls") }

    $defs = @()
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $match = [regex]::Match($lines[$i], '^function ([A-Za-z_][A-Za-z0-9_]*)\(')
        if ($match.Success) {
            $defs += [pscustomobject]@{ Index = $i; Name = $match.Groups[1].Value }
        }
    }

    $postRenderBody = ''
    $bodyStart = 0
    $bodyEnd = 0
    if ($render.Count -eq 1) {
        $following = @($defs | Where-Object { $_.Index -gt $render[0] })
        $bodyStart = $render[0] + 1
        if ($following.Count -gt 0) { $bodyEnd = $following[0].Index } else { $bodyEnd = $lines.Length }
        if ($bodyEnd -gt $bodyStart) {
            $postRenderLines = $bodyEnd - $bodyStart
            $postRenderBody = ($lines[$bodyStart..($bodyEnd - 1)] -join "`n")
        }
        if ($postRenderLines -lt 5 -or $postRenderLines -gt 200) {
            $problems.Add("postRender body has unexpected size ($postRenderLines lines)")
        }
        foreach ($expected in @('VanillaElseIfHell', 'LaserIndicator', 'TargetLaserIndicator')) {
            if (-not $postRenderBody.Contains($expected)) {
                $problems.Add("postRender body no longer references $expected")
            }
        }
    }

    for ($d = 0; $d -lt $defs.Count; $d++) {
        $start = $defs[$d].Index + 1
        if ($d + 1 -lt $defs.Count) { $end = $defs[$d + 1].Index } else { $end = $lines.Length }
        if ($end -le $start) { continue }
        $body = ($lines[$start..($end - 1)] -join "`n")
        if (-not $body.Contains('Isaac.Spawn(')) { continue }
        if (-not ([regex]::IsMatch($body, '\b1000\b') -and [regex]::IsMatch($body, '\b198\b'))) { continue }
        $name = $defs[$d].Name
        $spawnFunctions.Add($name)
        if ($postRenderBody -and -not [regex]::IsMatch($postRenderBody, '\b' + [regex]::Escape($name) + '\b')) {
            $problems.Add("indicator spawn function $name is not referenced from postRender")
        }
    }

    if ($spawnFunctions.Count -eq 0) {
        $problems.Add('no indicator spawn function found')
    }

    if ($render.Count -eq 1 -and $postRenderBody) {
        foreach ($dispatcher in $taskDispatchers) {
            $outside = @()
            for ($i = 0; $i -lt $lines.Length; $i++) {
                $line = $lines[$i]
                if (-not [regex]::IsMatch($line, '\b' + [regex]::Escape($dispatcher) + '\s*\(')) { continue }
                if ($line.Trim().StartsWith('function ')) { continue }
                if ($line.Trim().StartsWith('--')) { continue }
                $callLines.Add($i)
                if ($i -lt $bodyStart -or $i -ge $bodyEnd) { $outside += $i }
            }
            if ($outside.Count -gt 0) {
                $sample = ($outside | Select-Object -First 5) -join ', '
                $problems.Add("$dispatcher is called outside postRender (lines [$sample])")
            }
        }
    }

    return @{
        Ok = ($problems.Count -eq 0)
        Problems = @($problems)
        PostRenderLines = $postRenderLines
        SpawnFunctions = @($spawnFunctions)
        DispatcherCallLines = @($callLines)
    }
}

function Get-TaskPatch([byte[]]$Original, [bool]$AllowUnreviewedVersion = $false) {
    $text = $taskUtf8.GetString($Original)
    $digest = Get-TaskHash $Original
    $structure = Get-TaskStructure $text
    if (-not $structure.Ok) {
        throw ('Unexpected Watch out, laser! layout; no files were changed. ' + ($structure.Problems -join '; '))
    }
    if (-not $taskKnownSources.ContainsKey($digest) -and -not $AllowUnreviewedVersion) {
        throw 'Unsupported Watch out, laser! version; no files were changed. Run restore with the old tool, update this patch, or pass -AllowUnreviewed.'
    }

    $nl = Get-TaskNewline $text
    $payload = Get-TaskPayload $nl
    $gate = "    if isaacCoopStabilityShouldSkip() then$nl        return$nl    end$nl"
    $reset = "        isaacCoopStabilityBlocked = false$nl        isaacCoopStabilityDecided = false$nl"
    $renderAnchor = $taskRenderAnchor + $nl
    $startAnchor = $taskStartAnchor + $nl
    if (([regex]::Matches($text, [regex]::Escape($renderAnchor))).Count -ne 1 -or
        ([regex]::Matches($text, [regex]::Escape($startAnchor))).Count -ne 1) {
        throw 'Unexpected Watch out, laser! layout; no files were changed.'
    }
    $text = $text.Replace($renderAnchor, $payload + $renderAnchor + $gate)
    $text = $text.Replace($startAnchor, $startAnchor + $reset)
    $patched = $taskUtf8.GetBytes($text)
    $patchedText = $taskUtf8.GetString($patched)
    if ($patchedText.Contains($taskMarkerV1)) { throw 'internal patch verification failed: v1 marker' }
    if (([regex]::Matches($patchedText, [regex]::Escape($taskMarkerV2))).Count -ne 1) { throw 'internal patch verification failed: v2 marker' }
    if (([regex]::Matches($patchedText, [regex]::Escape($renderAnchor + $gate))).Count -ne 1) { throw 'internal patch verification failed: guard gate' }
    if (([regex]::Matches($patchedText, [regex]::Escape($startAnchor + $reset))).Count -ne 1) { throw 'internal patch verification failed: state reset' }
    if (-not $patchedText.Contains($taskMarkerV2End)) { throw 'internal patch verification failed: end marker missing' }
    return ,$patched
}

function Get-TaskRevertV1([byte[]]$Current) {
    $text = $taskUtf8.GetString($Current)
    $parts = [regex]::Split($text, '(?<=\n)')
    $begin = -1
    $end = -1
    for ($i = 0; $i -lt $parts.Length; $i++) {
        if ($begin -lt 0 -and $parts[$i].StartsWith('-- ' + $taskMarkerV1)) { $begin = $i }
        if ($end -lt 0 -and $parts[$i].StartsWith('-- ' + $taskMarkerV1End)) { $end = $i }
    }
    if ($begin -lt 0 -or $end -lt 0 -or $end -lt $begin) {
        throw 'v1 patch markers are missing or damaged; cannot reverse it.'
    }
    $kept = New-Object 'System.Collections.Generic.List[string]'
    for ($i = 0; $i -lt $begin; $i++) { $kept.Add($parts[$i]) }
    for ($i = $end + 1; $i -lt $parts.Length; $i++) { $kept.Add($parts[$i]) }
    $parts = $kept.ToArray()

    $signature = -1
    for ($i = 0; $i -lt $parts.Length; $i++) {
        if ($parts[$i].TrimEnd([char[]]"`r`n") -ceq $taskRenderAnchor) { $signature = $i; break }
    }
    $gateLines = @('    if isaacCoopStabilityShouldSkip() then', '        return', '    end')
    if ($signature -lt 0 -or $signature + 3 -ge $parts.Length) {
        throw 'v1 guard gate is missing; cannot reverse it.'
    }
    for ($g = 0; $g -lt 3; $g++) {
        if ($parts[$signature + 1 + $g].TrimEnd([char[]]"`r`n") -cne $gateLines[$g]) {
            throw 'v1 guard gate has unexpected content; cannot reverse it.'
        }
    }
    $kept = New-Object 'System.Collections.Generic.List[string]'
    for ($i = 0; $i -le $signature; $i++) { $kept.Add($parts[$i]) }
    for ($i = $signature + 4; $i -lt $parts.Length; $i++) { $kept.Add($parts[$i]) }
    $parts = $kept.ToArray()

    $anchor = -1
    for ($i = 0; $i -lt $parts.Length; $i++) {
        if ($parts[$i].TrimEnd([char[]]"`r`n") -ceq $taskStartAnchor) { $anchor = $i; break }
    }
    if ($anchor -lt 0 -or $anchor + 1 -ge $parts.Length) {
        throw 'v1 postGameStarted reset is missing; cannot reverse it.'
    }
    if ($parts[$anchor + 1].TrimEnd([char[]]"`r`n") -cne '        isaacCoopStabilityBlocked = false') {
        throw 'v1 postGameStarted reset has unexpected content; cannot reverse it.'
    }
    $kept = New-Object 'System.Collections.Generic.List[string]'
    for ($i = 0; $i -le $anchor; $i++) { $kept.Add($parts[$i]) }
    for ($i = $anchor + 2; $i -lt $parts.Length; $i++) { $kept.Add($parts[$i]) }
    $reverted = [string]::Join('', $kept.ToArray())
    if ($reverted.Contains($taskMarkerV1)) { throw 'v1 patch reversal left markers behind; cannot reverse it.' }
    return ,$taskUtf8.GetBytes($reverted)
}

function Assert-TaskGameClosed {
    if (Get-Process -Name 'isaac-ng' -ErrorAction SilentlyContinue) {
        throw 'Close Isaac before installing, verifying, or restoring this patch.'
    }
}

function Write-TaskAtomic([string]$Path, [byte[]]$Data) {
    $parent = [IO.Path]::GetDirectoryName($Path)
    $temp = Join-Path $parent ('.isaac-stability-' + [IO.Path]::GetRandomFileName())
    try {
        [IO.File]::WriteAllBytes($temp, $Data)
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temp, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temp, $Path) }
    }
    finally {
        if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
    }
}

function Read-TaskModVersion([string]$Directory) {
    try {
        $metadata = [xml][IO.File]::ReadAllText((Join-Path $Directory 'metadata.xml'), $taskUtf8)
        if ($metadata.metadata.version) { return [string]$metadata.metadata.version }
    }
    catch { }
    return 'unknown'
}

function Get-TaskBaseResult([string]$Source) {
    $directory = [IO.Path]::GetDirectoryName($Source)
    $bytes = [IO.File]::ReadAllBytes($Source)
    $backup = Join-Path $directory $taskBackupName
    $result = [ordered]@{
        status = 'unsupported_version'
        mod_dir = $directory
        mod_id = $taskWorkshopId
        mod_version = (Read-TaskModVersion $directory)
        guard_version = $null
        source_sha256 = (Get-TaskHash $bytes)
        original_sha256 = $null
        patched_sha256 = $null
        fingerprint = $null
        source_basis = $null
        unreviewed_source = $false
        backup_present = [IO.File]::Exists($backup)
        backup_matches_original = $false
        warnings = @()
    }
    return $result
}

function Get-TaskInspect([string]$Source) {
    $current = [IO.File]::ReadAllBytes($Source)
    $digest = Get-TaskHash $current
    $directory = [IO.Path]::GetDirectoryName($Source)
    $backupPath = Join-Path $directory $taskBackupName
    $result = Get-TaskBaseResult $Source
    $result.source_sha256 = $digest

    if ($digest -eq $taskOriginalHash) {
        $patched = Get-TaskPatch $current $false
        $patchedHash = Get-TaskHash $patched
        $result.status = 'original_supported'
        $result.original_sha256 = $digest
        $result.patched_sha256 = $patchedHash
        $result.fingerprint = Get-TaskFingerprint $patchedHash
        $result.source_basis = 'known_source'
        if ([IO.File]::Exists($backupPath)) {
            $result.backup_matches_original = ((Get-TaskHash ([IO.File]::ReadAllBytes($backupPath))) -eq $digest)
        }
        return $result
    }

    $currentText = $taskUtf8.GetString($current)
    if ($currentText.Contains($taskMarkerV2)) {
        if (-not [IO.File]::Exists($backupPath)) {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('backup_missing')
            return $result
        }
        $original = [IO.File]::ReadAllBytes($backupPath)
        $originalHash = Get-TaskHash $original
        $result.original_sha256 = $originalHash
        try {
            $expected = Get-TaskPatch $original $true
        }
        catch {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('cannot_verify_source')
            return $result
        }
        if ((Get-TaskHash $current) -ne (Get-TaskHash $expected)) {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('additional_edits')
            $result.backup_matches_original = ((Get-TaskHash ([IO.File]::ReadAllBytes($backupPath))) -eq $originalHash)
            return $result
        }
        $known = $taskKnownSources.ContainsKey($originalHash)
        $result.status = 'patched_verified'
        $result.guard_version = 2
        $result.patched_sha256 = (Get-TaskHash $expected)
        $result.fingerprint = Get-TaskFingerprint (Get-TaskHash $expected)
        $result.source_basis = $(if ($known) { 'known_source' } else { 'unreviewed_structure' })
        $result.unreviewed_source = (-not $known)
        $result.backup_matches_original = $true
        return $result
    }

    if ($currentText.Contains($taskMarkerV1)) {
        if (-not [IO.File]::Exists($backupPath)) {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('backup_missing')
            return $result
        }
        $original = [IO.File]::ReadAllBytes($backupPath)
        $originalHash = Get-TaskHash $original
        $result.original_sha256 = $originalHash
        try { $reverted = Get-TaskRevertV1 $current }
        catch {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('cannot_reverse_v1')
            return $result
        }
        if ((Get-TaskHash $reverted) -ne $originalHash) {
            $result.status = 'patched_needs_attention'
            $result.warnings = @('does_not_match_backup')
            return $result
        }
        $known = $taskKnownSources.ContainsKey($originalHash)
        $result.status = 'patched_v1_verified'
        $result.guard_version = 1
        $result.patched_sha256 = $digest
        $result.fingerprint = Get-TaskFingerprint $digest
        $result.source_basis = $(if ($known) { 'known_source' } else { 'unreviewed_structure' })
        $result.unreviewed_source = (-not $known)
        $result.backup_matches_original = $true
        return $result
    }

    $structure = Get-TaskStructure $currentText
    $result.structure_ok = [bool]$structure.Ok
    $result.structure_problems = @($structure.Problems)
    if ([IO.File]::Exists($backupPath)) {
        if ((Get-TaskHash ([IO.File]::ReadAllBytes($backupPath))) -ne $digest) {
            $result.warnings = @('stale_backup')
        }
        else {
            $result.warnings = @('existing_backup')
        }
    }
    return $result
}

function Update-TaskBackup([string]$Source, [byte[]]$Original) {
    $directory = [IO.Path]::GetDirectoryName($Source)
    $backup = Join-Path $directory $taskBackupName
    $originalHash = Get-TaskHash $Original
    if (-not [IO.File]::Exists($backup)) {
        $stream = [IO.File]::Open($backup, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($Original, 0, $Original.Length); $stream.Flush($true) }
        finally { $stream.Dispose() }
        return
    }
    $existing = [IO.File]::ReadAllBytes($backup)
    if ((Get-TaskHash $existing) -eq $originalHash) { return }
    $rotated = Join-Path $directory ($taskBackupName + '.' + (Get-TaskHash $existing).Substring(0, 8))
    if ([IO.File]::Exists($rotated)) { throw 'A rotated backup with the same hash already exists; resolve it manually.' }
    [IO.File]::Move($backup, $rotated)
    $stream = [IO.File]::Open($backup, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($Original, 0, $Original.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Invoke-TaskInstall([string]$Source) {
    Assert-TaskGameClosed
    $status = Get-TaskInspect $Source
    if ($status.status -eq 'patched_verified') {
        $result = Get-TaskInspect $Source
        $result.note = $taskInstallNote
        return $result
    }
    if ($status.status -eq 'patched_needs_attention') {
        throw ('Patched file needs attention: ' + ($status.warnings -join '; '))
    }

    $current = [IO.File]::ReadAllBytes($Source)
    $directory = [IO.Path]::GetDirectoryName($Source)
    if ($status.status -eq 'original_supported') {
        $original = $current
    }
    elseif ($status.status -eq 'patched_v1_verified') {
        $original = [IO.File]::ReadAllBytes((Join-Path $directory $taskBackupName))
    }
    else {
        $original = $current
    }

    $patched = Get-TaskPatch $original ([bool]$AllowUnreviewed)
    Update-TaskBackup $Source $original

    $known = $taskKnownSources.ContainsKey((Get-TaskHash $original))
    $manifest = [ordered]@{
        patch_version = $taskVersion
        tool_version = $taskToolVersion
        mod_id = $taskWorkshopId
        mod_version = (Read-TaskModVersion $directory)
        source_sha256 = (Get-TaskHash $original)
        patched_sha256 = (Get-TaskHash $patched)
        fingerprint = (Get-TaskFingerprint (Get-TaskHash $patched))
        source_basis = $(if ($known) { 'known_source' } else { 'unreviewed_structure' })
        backup_file = $taskBackupName
        requires_matching_patch_on_all_peers = $true
        created_utc = ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss', [Globalization.CultureInfo]::InvariantCulture) + '+00:00')
    }
    Write-TaskAtomic (Join-Path $directory $taskManifestName) ($taskUtf8.GetBytes((($manifest | ConvertTo-Json -Depth 5) + "`n")))

    Assert-TaskGameClosed
    if ((Get-TaskHash ([IO.File]::ReadAllBytes($Source))) -ne (Get-TaskHash $current)) {
        throw 'The mod changed while preparing the patch; source was not overwritten.'
    }
    Write-TaskAtomic $Source $patched
    $result = Get-TaskInspect $Source
    $result.note = $taskInstallNote
    return $result
}

function Invoke-TaskRestore([string]$Source) {
    Assert-TaskGameClosed
    $status = Get-TaskInspect $Source
    if ($status.status -eq 'original_supported') {
        $result = Get-TaskInspect $Source
        $result.note = $taskRestoreNote
        return $result
    }
    if ($status.status -ne 'patched_verified' -and $status.status -ne 'patched_v1_verified') {
        throw 'Current file is not a verified stability patch; refusing to overwrite it.'
    }

    $directory = [IO.Path]::GetDirectoryName($Source)
    $current = [IO.File]::ReadAllBytes($Source)
    $original = [IO.File]::ReadAllBytes((Join-Path $directory $taskBackupName))
    if ($status.status -eq 'patched_verified') {
        $expectedCurrent = Get-TaskPatch $original $true
        $changed = ((Get-TaskHash $current) -ne (Get-TaskHash $expectedCurrent))
    }
    else {
        $changed = ((Get-TaskHash (Get-TaskRevertV1 $current)) -ne (Get-TaskHash $original))
    }
    if ($changed) {
        throw 'The mod changed while preparing the restore; no files were changed.'
    }

    Assert-TaskGameClosed
    if ((Get-TaskHash ([IO.File]::ReadAllBytes($Source))) -ne (Get-TaskHash $current)) {
        throw 'The mod changed while preparing the restore; no files were changed.'
    }
    Write-TaskAtomic $Source $original
    $manifest = Join-Path $directory $taskManifestName
    if ([IO.File]::Exists($manifest)) { [IO.File]::Delete($manifest) }
    $result = Get-TaskInspect $Source
    $result.note = $taskRestoreNote
    return $result
}

function Invoke-TaskVerify([string]$Source) {
    $status = Get-TaskInspect $Source
    if ($status.status -ne 'patched_verified' -and $status.status -ne 'patched_v1_verified') {
        throw 'Patch is not installed; run install first.'
    }
    return [ordered]@{
        verify = 'ok'
        mod_dir = $status.mod_dir
        mod_version = $status.mod_version
        status = $status.status
        guard_version = $status.guard_version
        fingerprint = $status.fingerprint
        patched_sha256 = $status.patched_sha256
        note = $taskVerifyNote
    }
}

function Find-TaskSaveDir([string]$GameDirectory) {
    $info = Join-Path $GameDirectory 'savedatapath.txt'
    if ([IO.File]::Exists($info)) {
        foreach ($line in [IO.File]::ReadAllLines($info, $taskUtf8)) {
            $match = [regex]::Match($line.Trim(), '(?i)save data path\s*:\s*(.+)$')
            if ($match.Success) {
                $candidate = $match.Groups[1].Value.Trim().Replace('/', '\')
                if ([IO.Directory]::Exists($candidate)) { return $candidate }
            }
        }
    }
    $fallback = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\Binding of Isaac Repentance+'
    if ([IO.Directory]::Exists($fallback)) { return $fallback }
    return $null
}

function Get-TaskSessions([string]$SavePath) {
    if (-not $SavePath) { return @() }
    $root = Join-Path $SavePath 'online_logs\desyncs\sessions'
    if (-not [IO.Directory]::Exists($root)) { return @() }
    $sessions = @()
    foreach ($directory in [IO.Directory]::GetDirectories($root)) {
        $name = [IO.Path]::GetFileName($directory)
        $started = $null
        try {
            $parsed = [datetime]::ParseExact($name, 'MM_dd_yyyy__HH_mm_ss', [Globalization.CultureInfo]::InvariantCulture)
            $started = $parsed.ToString('yyyy-MM-ddTHH:mm:ss')
        }
        catch { }
        $log = Join-Path $directory 'log.txt'
        $lines = @()
        if ([IO.File]::Exists($log)) { $lines = [IO.File]::ReadAllLines($log, $taskUtf8) }
        $removals = @($lines | Where-Object { $_.Contains('NetDesyncHandler::RemoveUser') })
        $users = @()
        foreach ($line in $removals) {
            foreach ($match in [regex]::Matches($line, '\b7656\d{13}\b')) {
                if ($users -notcontains $match.Value) { $users += $match.Value }
            }
        }
        $users = @($users | Sort-Object)
        $hasBegin = @([IO.Directory]::GetFiles($directory, '*_begin.dat')).Count -gt 0
        $hasEnd = @([IO.Directory]::GetFiles($directory, '*_end.dat')).Count -gt 0
        $bytes = 0
        if ([IO.File]::Exists($log)) { $bytes = (Get-Item -LiteralPath $log).Length }
        $sessions += [ordered]@{
            name = $name
            started = $started
            remove_user_events = $removals.Count
            users = @($users)
            has_save_snapshots = ($hasBegin -and $hasEnd)
            bytes = $bytes
        }
    }
    return @($sessions | Sort-Object -Property { if ($_.started) { $_.started } else { '' } } -Descending)
}

function Invoke-TaskDiagnose([string]$Source) {
    $status = Get-TaskInspect $Source
    $gameDirectory = [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($Source))
    if ($SaveDir) {
        if ([IO.Directory]::Exists($SaveDir)) { $resolved = (Get-Item -LiteralPath $SaveDir).FullName }
        else { $resolved = $null }
    }
    else { $resolved = Find-TaskSaveDir $gameDirectory }

    $result = [ordered]@{
        patch = $status
        save_dir = $resolved
        guard_log_lines = @()
        main_log_remove_user_events = 0
        desync_sessions = [ordered]@{ dir = $null; total = 0; recent = @(); before_patch = $null; after_patch = $null }
        diff_files = @()
        notes = @('Session counts track NetDesyncHandler cleanup events, not proof that a specific entity caused a desync.')
    }
    if (-not $resolved -or -not [IO.Directory]::Exists($resolved)) {
        $result.notes = @($result.notes) + @('Save data directory not found; use -SaveDir to point at it.')
        return $result
    }

    $mainLog = Join-Path $resolved 'log.txt'
    $lines = @()
    if ([IO.File]::Exists($mainLog)) { $lines = [IO.File]::ReadAllLines($mainLog, $taskUtf8) }
    $guard = @($lines | Where-Object { $_.Contains('[ISAAC-STABILITY]') } | ForEach-Object { $_.Trim() })
    if ($guard.Count -gt 10) { $guard = @($guard[($guard.Count - 10)..($guard.Count - 1)]) }
    $result.guard_log_lines = @($guard)
    $result.main_log_remove_user_events = @($lines | Where-Object { $_.Contains('NetDesyncHandler::RemoveUser') }).Count

    $sessions = @(Get-TaskSessions $resolved)
    $sessionsDirectory = Join-Path $resolved 'online_logs\desyncs\sessions'
    $sessionsDirValue = $null
    if ([IO.Directory]::Exists($sessionsDirectory)) { $sessionsDirValue = $sessionsDirectory }
    $recent = @()
    if ($sessions.Count -gt 10) { $recent = @($sessions[0..9]) } else { $recent = @($sessions) }
    $result.desync_sessions = [ordered]@{
        dir = $sessionsDirValue
        total = $sessions.Count
        recent = @($recent)
        before_patch = $null
        after_patch = $null
    }

    $manifest = Join-Path ([IO.Path]::GetDirectoryName($Source)) $taskManifestName
    $installTime = $null
    if ([IO.File]::Exists($manifest)) {
        try {
            $parsed = [IO.File]::ReadAllText($manifest, $taskUtf8) | ConvertFrom-Json
            if ($parsed.created_utc) {
                $installTime = [datetime]::Parse($parsed.created_utc, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal)
            }
        }
        catch { }
    }
    if ($installTime) {
        $before = 0
        $after = 0
        foreach ($session in $sessions) {
            if (-not $session.started) { continue }
            $startedUtc = [datetime]::ParseExact(
                $session.started,
                'yyyy-MM-ddTHH:mm:ss',
                [Globalization.CultureInfo]::InvariantCulture,
                ([Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
            )
            if ($startedUtc -lt $installTime) { $before++ } else { $after++ }
        }
        $result.desync_sessions.before_patch = $before
        $result.desync_sessions.after_patch = $after
    }

    $diffFiles = @()
    $found = @(Get-ChildItem -LiteralPath $resolved -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*diff*.txt' } | Sort-Object FullName)
    foreach ($file in ($found | Select-Object -First 20)) {
        $relative = $file.FullName.Substring($resolved.Length + 1).Replace('\', '/')
        $diffFiles += [ordered]@{ path = $relative; bytes = $file.Length }
    }
    $result.diff_files = @($diffFiles)
    return $result
}

try {
    if (-not $ModDir) {
        $steam = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam').SteamPath
        if (-not $steam) { throw 'Steam was not found; use -ModDir.' }
        $roots = @($steam)
        $libraryFile = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $libraryFile) {
            $libraryText = [IO.File]::ReadAllText($libraryFile)
            foreach ($match in [regex]::Matches($libraryText, '"path"\s+"([^"]+)"')) {
                $roots += $match.Groups[1].Value.Replace('\\', '\')
            }
        }
        $found = @()
        foreach ($root in ($roots | Select-Object -Unique)) {
            $appManifest = Join-Path $root 'steamapps\appmanifest_250900.acf'
            if (-not (Test-Path -LiteralPath $appManifest)) { continue }
            $match = [regex]::Match([IO.File]::ReadAllText($appManifest), '"installdir"\s+"([^"]+)"')
            if ($match.Success) {
                $mods = Join-Path $root ('steamapps\common\' + $match.Groups[1].Value + '\mods')
                if (Test-Path -LiteralPath $mods) {
                    $found += @(Get-ChildItem -LiteralPath $mods -Directory | Where-Object { $_.Name.EndsWith($taskWorkshopId) } | ForEach-Object { $_.FullName })
                }
            }
        }
        $found = @($found | Select-Object -Unique)
        if ($found.Count -ne 1) { throw 'Found a different number of matching mod directories; use -ModDir.' }
        $ModDir = $found[0]
    }

    $resolvedMod = (Get-Item -LiteralPath $ModDir).FullName
    [xml]$metadata = [IO.File]::ReadAllText((Join-Path $resolvedMod 'metadata.xml'), $taskUtf8)
    if ([string]$metadata.metadata.id -ne $taskWorkshopId) {
        throw 'The selected directory is not Watch out, laser! (2887926286).'
    }
    $source = Join-Path $resolvedMod 'main.lua'
    $sourceItem = Get-Item -LiteralPath $source
    if ($sourceItem.PSIsContainer -or ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'main.lua must be a regular file inside the selected mod directory.'
    }

    switch ($Action) {
        'status' { $result = Get-TaskInspect $source }
        'install' { $result = Invoke-TaskInstall $source }
        'restore' { $result = Invoke-TaskRestore $source }
        'verify' { $result = Invoke-TaskVerify $source }
        'diagnose' { $result = Invoke-TaskDiagnose $source }
    }

    $result | ConvertTo-Json -Depth 8
    if ($Action -eq 'status' -and $taskHealthy -notcontains $result.status) { exit 1 }
}
catch {
    Write-Error $_
    exit 1
}
