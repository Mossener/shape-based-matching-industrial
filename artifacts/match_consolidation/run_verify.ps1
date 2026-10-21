param([switch]$Run,[switch]$Minimal,[switch]$SkipCompile,[string]$Output='artifacts/match_consolidation/verification.csv')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH='D:\opencv-4.12.0\build\bin;F:\mysys2\ucrt64\bin;'+$env:PATH
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_WAIT_POLICY='PASSIVE'
$compiler='F:\mysys2\ucrt64\bin\g++.exe'
$build=Join-Path $PSScriptRoot 'build';New-Item -ItemType Directory -Path $build -Force|Out-Null
$executable=Join-Path $build 'verify.exe'
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP','-ID:/opencv-4.12.0/build')
foreach($m in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-ID:/opencv-4.12.0/modules/$m/include"}
$sources=@('line2Dup.cpp','line2Dup.h','line2Dup_matches.hpp','line2Dup_local.hpp','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
    'artifacts/match_consolidation/verify.cpp','artifacts/match_consolidation/run_verify.ps1',
    'artifacts/search_optimization/fixtures.hpp','artifacts/led_match/led_demo.cpp',
    'tests/search_reference_matcher.cpp','tests/search_reference_matcher.hpp',
    'artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h',
    'artifacts/local_center_optimization/v10_reference.cpp','artifacts/local_center_optimization/v10_reference.hpp',
    'datasets/tless_tiny/index.json','datasets/tless_train_f32/templates_tless_object_1.yml.gz')
$repo=(Get-Location).Path
$sources+=Get-ChildItem -LiteralPath artifacts/local_center_optimization/baseline -Recurse -File|ForEach-Object{$_.FullName.Substring($repo.Length+1).Replace('\','/')}
function Hashes {$r=[ordered]@{};foreach($p in $sources){$r[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash};return $r}
$hashes=Hashes
if(-not $SkipCompile){
    $units=@(
        @{source='line2Dup.cpp';target=(Join-Path $build 'current.o');frozen=$false},
        @{source='tests/search_reference_matcher.cpp';target=(Join-Path $build 'v4.o');frozen=$false},
        @{source='artifacts/local_center_optimization/v10_reference.cpp';target=(Join-Path $build 'v10.o');frozen=$true},
        @{source='artifacts/match_consolidation/verify.cpp';target=(Join-Path $build 'verify.o');frozen=$false})
    foreach($u in $units){$f=$flags;if($u.frozen){$f=@($flags|Where-Object{$_ -ne '-IMIPP'})+@('-Iartifacts/local_center_optimization/baseline/MIPP')}
        & $compiler @f '-c' $u.source '-o' $u.target;if($LASTEXITCODE -ne 0){throw "Compile failed $($u.source)"}}
    $objects=@($units|ForEach-Object{$_.target});& $compiler '-fopenmp' @objects '-LD:/opencv-4.12.0/build/lib' '-lopencv_world4120' '-o' $executable
    if($LASTEXITCODE -ne 0){throw 'Link failed'}
    @{source_sha256=$hashes;executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $build 'manifest.json') -Encoding UTF8
}else{
    $m=Get-Content -LiteralPath (Join-Path $build 'manifest.json') -Raw|ConvertFrom-Json
    foreach($p in $sources){if($m.source_sha256.$p -ne $hashes[$p]){throw "Source changed since compilation: $p"}}
    if($m.executable_sha256 -ne (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash){throw 'Executable changed'}
}
if(-not $Run){Write-Output 'Compiled without matching. Use -Run after CPU coordination.';return}
if(Test-Path -LiteralPath $Output){throw 'Output exists; choose a fresh path'}
$argv=@('--output',$Output);if($Minimal){$argv+='--minimal'}
& $executable @argv
$code=$LASTEXITCODE
$after=Hashes;foreach($p in $sources){if($hashes[$p] -ne $after[$p]){throw "Source changed during verification: $p"}}
@{completed_at=(Get-Date -Format o);exit_code=$code;source_sha256=$hashes;cv_threads=1;omp_thread_matrix=@(1,4,2,4);repeats_per_variant=2;minimal=[bool]$Minimal;
  csv_sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash;executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath ($Output+'.provenance.json') -Encoding UTF8
if($code -ne 0){throw "Verification failed: $code"}
