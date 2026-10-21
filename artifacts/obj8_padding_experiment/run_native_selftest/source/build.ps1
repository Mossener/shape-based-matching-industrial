param(
    [string]$Compiler = 'F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV = 'D:\opencv-4.12.0',
    [string]$SourceRevision = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH = "$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$build = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$revision = (& git rev-parse --verify $SourceRevision).Trim()
if($LASTEXITCODE -ne 0) { throw 'Cannot resolve requested committed core' }
$snapshot = Join-Path $build ('core_source_' + $revision.Substring(0,12))
@'
import pathlib, subprocess, sys
revision = sys.argv[1]
destination = pathlib.Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)
names = [name for name in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', revision]).decode().splitlines()
         if '/' not in name and name.startswith('line2Dup') and pathlib.Path(name).suffix in ('.cpp', '.h', '.hpp')]
for name in names:
    (destination / name).write_bytes(subprocess.check_output(['git', 'show', revision + ':' + name]))
'@ | & python - $SourceRevision $snapshot
if($LASTEXITCODE -ne 0) { throw 'Cannot snapshot the requested committed core' }
$sources = @((Get-ChildItem -LiteralPath $snapshot -File | ForEach-Object {$_.FullName})) + @(
    'MIPP/mipp.h','artifacts/public_evaluation/tless_eval.cpp','artifacts/public_evaluation/eval_metrics.hpp','artifacts/public_evaluation/build.ps1')
$before = [ordered]@{}
foreach($source in $sources) { $before[$source] = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
$flags = @('-std=c++17','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare',"-I$snapshot",'-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) { $flags += "-I$OpenCV/modules/$module/include" }
$executable = Join-Path $build 'tless_eval.exe'
& $Compiler @flags (Join-Path $snapshot 'line2Dup.cpp') 'artifacts/public_evaluation/tless_eval.cpp' "-L$OpenCV/build/lib" '-lopencv_world4120' '-lz' '-o' $executable
if($LASTEXITCODE -ne 0) { throw 'T-LESS adapter compile failed' }
foreach($source in $sources) {
    if($before[$source] -ne (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash) { throw "Source changed while compiling: $source" }
}
@{compiled_at=(Get-Date -Format o);core_git_revision=$revision;source_sha256=$before;compiler=$Compiler;flags=$flags;
  executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash} |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Encoding UTF8
Write-Output 'Compiled adapter only. No matching has run. Coordinate CPU before develop/final.'
