# Remove only individually verified duplicate members; never recursive deletion.
param([ValidateSet('v1','v2')][string]$Revision='v1')
$ErrorActionPreference = 'Stop'
$duplicateRoot = 'D:\Coding\ISAAC\authority\build-ui-incremental2\unpack-native-' + $Revision
$retainedArchive = 'D:\Coding\ISAAC\authority\artifacts\isaac-incremental2-native-effects-' + $Revision + '.zip'
$cleanupReport = 'D:\Coding\ISAAC\authority\reports\ui-incremental2-stage1\unpacked-replay-' + $Revision + '-cleanup.json'
if ((Resolve-Path -LiteralPath $duplicateRoot).Path -ne $duplicateRoot) { throw 'Unexpected extraction root' }
$archiveExpectedHash = ((Get-Content -LiteralPath ($retainedArchive + '.sha256') -Raw) -split '\s+')[0]
if ($archiveExpectedHash -notmatch '^[a-f0-9]{64}$' -or (Get-FileHash -LiteralPath $retainedArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archiveExpectedHash) { throw 'Retained archive changed' }
$archiveReader = [IO.Compression.ZipFile]::OpenRead($retainedArchive)
try {
    $manifestEntry = $archiveReader.GetEntry('bundle-manifest.json')
    $manifestReader = [IO.StreamReader]::new($manifestEntry.Open())
    try { $manifestText = $manifestReader.ReadToEnd() } finally { $manifestReader.Dispose() }
    if ((Get-Content -LiteralPath (Join-Path $duplicateRoot 'bundle-manifest.json') -Raw) -cne $manifestText) { throw 'Extracted manifest changed' }
    $bundleManifest = $manifestText | ConvertFrom-Json
} finally { $archiveReader.Dispose() }
$allItems = @(Get-ChildItem -LiteralPath $duplicateRoot -Force -Recurse)
if ($allItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Reparse point in extraction' }
$expectedFiles = @($bundleManifest.files | ForEach-Object {
    $memberPath = [IO.Path]::GetFullPath((Join-Path $duplicateRoot $_.path))
    if (-not $memberPath.StartsWith($duplicateRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Member escapes extraction' }
    if ((Get-FileHash -LiteralPath $memberPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256) { throw ('Changed duplicate: ' + $_.path) }
    $memberPath
}) + (Join-Path $duplicateRoot 'bundle-manifest.json')
if (@($allItems | Where-Object { -not $_.PSIsContainer }).Count -ne $expectedFiles.Count) { throw 'Unique result found in extraction' }
$removedBytes = ($allItems | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum
foreach ($verifiedFile in $expectedFiles) { Remove-Item -LiteralPath $verifiedFile -Force }
foreach ($emptyFolder in ($allItems | Where-Object PSIsContainer | Sort-Object { $_.FullName.Length } -Descending)) {
    if (@(Get-ChildItem -LiteralPath $emptyFolder.FullName -Force).Count -ne 0) { throw 'Directory is no longer empty' }
    Remove-Item -LiteralPath $emptyFolder.FullName
}
if (@(Get-ChildItem -LiteralPath $duplicateRoot -Force).Count -ne 0) { throw 'Extraction root is no longer empty' }
Remove-Item -LiteralPath $duplicateRoot
[ordered]@{ extraction_removed = -not (Test-Path -LiteralPath $duplicateRoot); files_removed = $expectedFiles.Count; bytes_removed = $removedBytes; unique_results_retained = ('unpacked-replay-' + $Revision); method = 'individually hash-verified files, then empty directories'; recursive_delete_used = $false } | ConvertTo-Json | Set-Content -LiteralPath $cleanupReport -Encoding utf8
