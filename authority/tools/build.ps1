param([switch]$SkipTests, [string]$BuildDirectory = 'build', [string]$RuntimeOutputDirectory, [switch]$TraceResearch, [switch]$SliceResearch, [switch]$Slice2Research, [switch]$Slice3Research, [switch]$Slice3UiResearch, [switch]$BoundedUiResearch, [switch]$IncrementalUiResearch, [ValidateSet(2000000,5000000,10000000)][int]$IncrementalWorkLimit=5000000, [switch]$AllowGameRunning)
$ErrorActionPreference = 'Stop'
if (-not $AllowGameRunning -and (Get-Process -Name 'isaac-ng' -ErrorAction SilentlyContinue)) {
    throw 'Isaac is running; close it before building (the injected probe DLL is loaded and cannot be overwritten). Use -AllowGameRunning only if you are sure the target DLL is not in use.'
}
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$taskVs = & $taskVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $taskVs) { throw 'MSVC x86 tools are required.' }
$taskCmake = Join-Path $taskVs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if (-not (Test-Path -LiteralPath $taskCmake)) { $taskCmake = (Get-Command cmake).Source }
$taskBuild = if ([IO.Path]::IsPathRooted($BuildDirectory)) { $BuildDirectory } else { Join-Path $taskRoot $BuildDirectory }
$taskCmakeArguments=@('-S',$taskRoot,'-B',$taskBuild,'-G','Visual Studio 18 2026','-A','Win32')
$taskRuntimeOutput=if(-not $RuntimeOutputDirectory){Join-Path $taskBuild 'Release'}elseif([IO.Path]::IsPathRooted($RuntimeOutputDirectory)) { $RuntimeOutputDirectory } else { Join-Path $taskRoot $RuntimeOutputDirectory }
$taskCmakeArguments+=('-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE='+$taskRuntimeOutput)
$taskCmakeArguments+=('-DIA_BUILD_TRACE_RESEARCH='+$(if($TraceResearch){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_SLICE_RESEARCH='+$(if($SliceResearch){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_SLICE2_RESEARCH='+$(if($Slice2Research){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_SLICE3_RESEARCH='+$(if($Slice3Research){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_SLICE3_UI_RESEARCH='+$(if($Slice3UiResearch){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_BOUNDED_UI_RESEARCH='+$(if($BoundedUiResearch){'ON'}else{'OFF'}))
$taskCmakeArguments+=('-DIA_BUILD_INCREMENTAL_UI_RESEARCH='+$(if($IncrementalUiResearch){'ON'}else{'OFF'}))
if($IncrementalUiResearch){$taskCmakeArguments+=('-DIA_INCREMENTAL_WORK_LIMIT='+$IncrementalWorkLimit)}
& $taskCmake @taskCmakeArguments
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed.' }
& $taskCmake --build $taskBuild --config Release --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
if (-not $SkipTests) {
    & (Join-Path $taskRuntimeOutput 'authority-tests.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Native tests failed.' }
    & (Join-Path $taskRuntimeOutput 'authority-state-tests.exe')
    if ($LASTEXITCODE -ne 0) { throw 'State model tests failed.' }
}
