param([switch]$Run,[switch]$SkipCompile,[string]$Output='artifacts/match_consolidation/timing_v11')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH='D:\opencv-4.12.0\build\bin;F:\mysys2\ucrt64\bin;'+$env:PATH
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_WAIT_POLICY='PASSIVE';$env:OMP_MAX_ACTIVE_LEVELS='1'
$compiler='F:\mysys2\ucrt64\bin\g++.exe';$build=Join-Path $PSScriptRoot 'build'
$executable=Join-Path $build 'timing.exe'
& py -3.10 artifacts/match_consolidation/generate_stage_probe.py
if($LASTEXITCODE -ne 0){throw 'Stage diagnostic generation failed'}
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP','-ID:/opencv-4.12.0/build')
foreach($m in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-ID:/opencv-4.12.0/modules/$m/include"}
$verification=Get-Content -LiteralPath (Join-Path $build 'manifest.json') -Raw|ConvertFrom-Json
$hashes=[ordered]@{}
foreach($entry in $verification.source_sha256.PSObject.Properties){
    if($entry.Value -ne (Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash){throw "Verification input/source changed: $($entry.Name)"}
    $hashes[$entry.Name]=$entry.Value
}
$extra=@('artifacts/match_consolidation/timing.cpp','artifacts/match_consolidation/stage_reference.cpp','artifacts/match_consolidation/stage_reference.hpp',
    'artifacts/match_consolidation/generate_stage_probe.py','artifacts/match_consolidation/run_timing.ps1')
$repo=(Get-Location).Path
$extra+=Get-ChildItem -LiteralPath artifacts/match_consolidation/build/stage_source -File|ForEach-Object{$_.FullName.Substring($repo.Length+1).Replace('\','/')}
foreach($p in $extra){$hashes[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash}
$inputPaths=@('LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png','datasets/tless_train_f32/templates_tless_object_1.yml.gz','datasets/tless_tiny/index.json')
for($i=1;$i -le 8;$i++){$inputPaths+="LED/$i.bmp"}
$inputPaths+=@('datasets/tless_tiny/test_primesense/000005/rgb/000007.png','datasets/tless_tiny/test_primesense/000005/rgb/000070.png',
    'datasets/tless_tiny/test_primesense/000002/rgb/000003.png','datasets/tless_tiny/test_primesense/000002/rgb/000092.png')
$inputHashes=[ordered]@{};foreach($p in $inputPaths){$inputHashes[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash}
$manifest=Join-Path $build 'timing_manifest.json'
if(-not $SkipCompile){
    $frozenFlags=@($flags|Where-Object{$_ -ne '-IMIPP'})+@('-Iartifacts/local_center_optimization/baseline/MIPP')
    & $compiler @frozenFlags '-c' artifacts/match_consolidation/stage_reference.cpp '-o' (Join-Path $build 'stage.o')
    if($LASTEXITCODE -ne 0){throw 'Stage compile failed'}
    & $compiler @flags '-c' artifacts/match_consolidation/timing.cpp '-o' (Join-Path $build 'timing.o')
    if($LASTEXITCODE -ne 0){throw 'Timing compile failed'}
    $objects=@('current.o','v4.o','v10.o','stage.o','timing.o')|ForEach-Object{Join-Path $build $_}
    & $compiler '-fopenmp' @objects '-LD:/opencv-4.12.0/build/lib' '-lopencv_world4120' '-o' $executable
    if($LASTEXITCODE -ne 0){throw 'Timing link failed'}
    @{source_sha256=$hashes;input_sha256=$inputHashes;executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash}|
        ConvertTo-Json -Depth 8|Set-Content -LiteralPath $manifest -Encoding UTF8
}else{
    $saved=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json
    foreach($p in $hashes.Keys){if($saved.source_sha256.$p -ne $hashes[$p]){throw "Timing source changed since compilation: $p"}}
    if($saved.executable_sha256 -ne (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash){throw 'Timing executable changed'}
}
if(-not $Run){Write-Output 'Timing executable compiled without matching; coordinate exclusive CPU before -Run.';return}
if((Test-Path -LiteralPath ($Output+'_total.csv')) -or (Test-Path -LiteralPath ($Output+'_stage.csv'))){throw 'Choose fresh timing output prefix'}
@{started_at=(Get-Date -Format o);source_sha256=$hashes;input_sha256=$inputHashes;compiler=$compiler;compiler_flags=$flags;
  executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash;cv_threads=1;omp_threads=4;omp_wait_policy=$env:OMP_WAIT_POLICY;
  cold=1;warmup=2;measured=7;diagnostic_total_use='forbidden: contains extra sort/copy; stage fields only';
  current_v10_total='uninstrumented production and exact frozen V10, alternating case order'}|
    ConvertTo-Json -Depth 8|Set-Content -LiteralPath ($Output+'_environment.json') -Encoding UTF8
& $executable '--output' $Output
$code=$LASTEXITCODE
foreach($p in $hashes.Keys){if($hashes[$p] -ne (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash){throw "Source changed during timing: $p"}}
foreach($p in $inputHashes.Keys){if($inputHashes[$p] -ne (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash){throw "Input changed during timing: $p"}}
@{completed_at=(Get-Date -Format o);exit_code=$code;sources_unchanged=$true;inputs_unchanged=$true;
  total_csv_sha256=(Get-FileHash -LiteralPath ($Output+'_total.csv') -Algorithm SHA256).Hash;
  stage_csv_sha256=(Get-FileHash -LiteralPath ($Output+'_stage.csv') -Algorithm SHA256).Hash}|
    ConvertTo-Json|Set-Content -LiteralPath ($Output+'_completion.json') -Encoding UTF8
if($code -ne 0){throw "Timing output verification failed $code"}
