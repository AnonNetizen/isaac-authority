[CmdletBinding()]
param(
    [string]$Report = (Join-Path $PSScriptRoot '..\reports\cleanup-20261011.json'),
    [switch]$PrepareOnly,
    [switch]$ApplyPrepared
)
$ErrorActionPreference = 'Stop'
$taskRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\')
$rootPrefix = $taskRoot + '\'
$reportPath = [System.IO.Path]::GetFullPath($Report)
$verifier = Join-Path $PSScriptRoot 'cleanup_artifacts.py'
$journalPath = [System.IO.Path]::ChangeExtension($reportPath, '.deleted.jsonl')

function Get-CheckedTarget([string]$Relative) {
    if ([System.IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':')) {
        throw "Target must be a relative workspace path: $Relative"
    }
    $target = [System.IO.Path]::GetFullPath((Join-Path $taskRoot $Relative))
    if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target escapes workspace: $Relative"
    }
    $ancestor = $target
    while ($ancestor.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse point in cleanup path: $ancestor"
            }
        }
        $ancestor = [System.IO.Path]::GetDirectoryName($ancestor)
    }
    return $target
}

if (-not $reportPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Report must stay inside workspace'
}
Get-CheckedTarget ($reportPath.Substring($rootPrefix.Length)) | Out-Null
$active = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(authority.*|cl|link|MSBuild|cmake|ninja)\.exe$' -and
    (($_.ExecutablePath -and $_.ExecutablePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) -or
     ($_.CommandLine -and $_.CommandLine.Contains($taskRoot)))
})
if ($active.Count) { throw 'Project build or research process is active; no files were deleted' }
if (-not $ApplyPrepared) {
    & python -B $verifier prepare --report $reportPath
    if ($LASTEXITCODE -ne 0) { throw 'Candidate preparation failed; no files were deleted' }
}
if ($PrepareOnly) { return }
$plan = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($plan.schema -ne 'isaac-verified-cleanup-1' -or $plan.workspace -ne $taskRoot -or $plan.status -ne 'prepared') {
    throw 'Unexpected cleanup plan'
}
if (Test-Path -LiteralPath $journalPath) { throw 'Existing deletion journal is preserved; refusing to overwrite' }

# Preflight every concrete path and every retained archive before the first deletion.
$archiveByPath = @{}
foreach ($archive in $plan.archives) {
    $archiveByPath[$archive.path] = $archive
    $target = Get-CheckedTarget $archive.path
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archive.sha256) {
        throw "Retained archive changed: $target"
    }
}
$protectedPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($property in $plan.protected.PSObject.Properties) { [void]$protectedPaths.Add($property.Name) }
$cacheSuffixes = @('.obj','.pch','.ipch','.idb','.ilk','.tlog','.lastbuildstate')
foreach ($candidate in $plan.candidates) {
    $target = Get-CheckedTarget $candidate.path
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Candidate missing: $target" }
    switch ($candidate.reason) {
        'verified_package_duplicate' {
            $archive = $archiveByPath[$candidate.archive]
            if ($null -eq $archive -or -not $candidate.path.StartsWith(($archive.extraction + '/'), [System.StringComparison]::Ordinal)) {
                throw "Duplicate is outside its verified extraction: $target"
            }
        }
        'compiler_cache' {
            if ($candidate.path -notmatch '^authority/build(?:-[^/]+)?/' -or
                [System.IO.Path]::GetExtension($target).ToLowerInvariant() -notin $cacheSuffixes) {
                throw "Unexpected compiler cache: $target"
            }
        }
        'python_cache' {
            if ($candidate.path -notmatch '(^|/)__pycache__/[^/]+\.pyc$' -or $candidate.path -match '^(\.tools|artifacts)/') {
                throw "Unexpected Python cache: $target"
            }
        }
        default { throw "Unknown deletion reason: $target" }
    }
    if ($protectedPaths.Contains($candidate.path)) { throw "Protected deletion target: $target" }
}
$stream = [System.IO.StreamWriter]::new($journalPath, $false, [System.Text.UTF8Encoding]::new($false))
$parents = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$deleted = 0
$failure = $null
try {
    foreach ($candidate in $plan.candidates) {
        $target = Get-CheckedTarget $candidate.path
        $file = Get-Item -LiteralPath $target -Force
        if ($file.Length -ne $candidate.bytes -or
            (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $candidate.sha256) {
            throw "Candidate changed after verification: $target"
        }
        # Files only: no recursive deletion, shell switching or constructed commands.
        Remove-Item -LiteralPath $target -Force -Confirm:$false
        $stream.WriteLine((@{ operation='delete_file'; path=$candidate.path; sha256=$candidate.sha256 } | ConvertTo-Json -Compress))
        $parent = [System.IO.Path]::GetDirectoryName($target)
        while ($parent.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            [void]$parents.Add($parent)
            $parent = [System.IO.Path]::GetDirectoryName($parent)
        }
        $deleted++
        if ($deleted % 500 -eq 0) {
            $stream.Flush()
            Write-Output "Deleted verified files: $deleted / $($plan.candidates.Count)"
        }
    }
    foreach ($directory in ($parents | Sort-Object Length -Descending)) {
        $relative = $directory.Substring($rootPrefix.Length).Replace('\','/')
        Get-CheckedTarget $relative | Out-Null
        # Only empty descendants of the extraction/cache roots may disappear.
        $allowed = $relative -match '(^|/)__pycache__(/|$)' -or $relative -match '^authority/build(?:-[^/]+)?/'
        foreach ($archive in $plan.archives) {
            if ($relative -eq $archive.extraction -or $relative.StartsWith(($archive.extraction + '/'), [System.StringComparison]::Ordinal)) { $allowed = $true }
        }
        if ($allowed -and (Test-Path -LiteralPath $directory -PathType Container) -and
            -not (Get-ChildItem -LiteralPath $directory -Force | Select-Object -First 1)) {
            # Non-recursive even if another process creates a child after the check.
            [System.IO.Directory]::Delete($directory, $false)
            $stream.WriteLine((@{ operation='delete_empty_directory'; path=$relative } | ConvertTo-Json -Compress))
        }
    }
} catch {
    $failure = $_
} finally {
    $stream.Dispose()
}
& python -B $verifier finish --report $reportPath
if ($failure) { throw $failure }
if ($LASTEXITCODE -ne 0) { throw 'Cleanup verification failed; inspect the report' }
