param([Parameter(Mandatory=$true)][string]$Plan)
$ErrorActionPreference='Stop'
$cleanupPlan=Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
$cleanupRoot=(Resolve-Path -LiteralPath $cleanupPlan.root).Path
$allowedParent='D:\Coding\ISAAC\authority\build-ui-incremental2\compact\'
if (-not $cleanupRoot.StartsWith($allowedParent,[StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup target outside compact build' }
if ((Get-Item -LiteralPath $cleanupRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Extraction root is a reparse point' }
$allItems=@(Get-ChildItem -LiteralPath $cleanupRoot -Force -Recurse)
if ($allItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Extraction contains a reparse point' }
$files=@($cleanupPlan.files | ForEach-Object {
    $target=[IO.Path]::GetFullPath((Join-Path $cleanupRoot $_.path))
    if (-not $target.StartsWith($cleanupRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Member escapes extraction root' }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256) { throw ('Changed extraction member: '+$_.path) }
    $target
})
if (@($allItems | Where-Object { -not $_.PSIsContainer }).Count -ne $files.Count) { throw 'Unique files found; preserve extraction' }
$removedBytes=($allItems | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum
foreach ($duplicate in $files) { Remove-Item -LiteralPath $duplicate -Force }
foreach ($folder in ($allItems | Where-Object PSIsContainer | Sort-Object { $_.FullName.Length } -Descending)) {
    if (@(Get-ChildItem -LiteralPath $folder.FullName -Force).Count) { throw 'Directory gained new files' }
    Remove-Item -LiteralPath $folder.FullName
}
if (@(Get-ChildItem -LiteralPath $cleanupRoot -Force).Count) { throw 'Extraction gained new files' }
Remove-Item -LiteralPath $cleanupRoot
[ordered]@{extraction_removed=$true;verified_duplicate_files=$files.Count;bytes_removed=$removedBytes;recursive_delete_used=$false;results_retained_outside_extraction=$true} | ConvertTo-Json | Set-Content -LiteralPath ($Plan+'.result.json') -Encoding utf8
