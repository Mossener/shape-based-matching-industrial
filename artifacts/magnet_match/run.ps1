param(
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0',
    [string]$OutputDirectory='artifacts/magnet_match/run_20261021_initial',
    [switch]$Run,
    [switch]$Diagnose,
    [switch]$Validate
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
if(Test-Path -LiteralPath $OutputDirectory){throw 'Output directory must be new; preserve prior runs'}
if($Diagnose -and $Validate){throw 'Choose Diagnose or Validate'}
if($OutputDirectory -match '[^\x00-\x7F]'){throw 'Use an ASCII output path for this OpenCV build'}
& py -3.10 artifacts/magnet_match/inspect_smd.py
if($LASTEXITCODE -ne 0){throw 'SMD structure/SHA inspection failed'}
$env:PATH="$(Split-Path -Parent $Compiler);$OpenCV\build\bin;$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
$sources=@('line2Dup.cpp','line2Dup.h','line2Dup_matches.hpp','line2Dup_local.hpp','line2Dup_search.hpp','line2Dup_response.hpp','line2Dup_spread.hpp',
    'artifacts/magnet_match/magnet_demo.cpp','artifacts/magnet_match/inspect_smd.py','artifacts/magnet_match/evaluate.py','artifacts/magnet_match/run.ps1')
$sources+=@(Get-ChildItem -LiteralPath MIPP -File -Recurse | ForEach-Object {$_.FullName})
$before=[ordered]@{}
foreach($path in $sources){$before[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$inputs=[ordered]@{}
foreach($path in (Get-ChildItem -LiteralPath 'artifacts/magnet_match/build/input' -File)){$inputs[$path.FullName]=(Get-FileHash -LiteralPath $path.FullName -Algorithm SHA256).Hash}
if($Validate){$inputs['artifacts/magnet_match/manual_boxes.json']=(Get-FileHash -LiteralPath 'artifacts/magnet_match/manual_boxes.json' -Algorithm SHA256).Hash}
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-I$OpenCV/modules/$module/include"}
$exe='artifacts/magnet_match/build/magnet_demo.exe'
& $Compiler @flags line2Dup.cpp artifacts/magnet_match/magnet_demo.cpp "-L$OpenCV/build/lib" '-lopencv_world4120' '-o' $exe
if($LASTEXITCODE -ne 0){throw 'Compile failed'}
if(-not $Run){Write-Output 'Compiled only. Pass -Run after coordinating CPU.';exit}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$config=@{threshold=75;angle_step_degrees=2;scales=@(.90,.95,1,1.05,1.10);levels=@(2,3,4);templates_per_configuration=900;
  image_size=@(640,480);padded_size=@(768,640);padding_left_top=64;padding_bottom=96;
  repeats=1;warmups=0;opencv_threads=1;openmp_threads=4;timing_scope='Single diagnostic internal call; not a paired performance benchmark';
  source_image='M01.bmp';test_images=@('M02.bmp','M03.bmp','M04.bmp','M05.bmp','M06.bmp','M07.bmp');
  direction='theta=(-stored_angle-pose_angle) mod 360; modulo180 labels';options='Current defaults, including fused_local_search';
  limitation='No localization GT or negative images; no accuracy claim; fixed scale range may not cover all samples'}
if($Diagnose){$config=@{mode='focused_diagnostic';threshold=75;opencv_threads=1;openmp_threads=4;cases=@(
    @{case='L4_source_pad64';levels=4;image='M01.bmp';padding=64;scale=1;angles=@(0)},
    @{case='L4_source_pad256';levels=4;image='M01.bmp';padding=256;scale=1;angles=@(0)},
    @{case='L3_M04_scale070';levels=3;image='M04.bmp';padding=128;scale=.7;angle_step=2},
    @{case='L3_M06_scale125';levels=3;image='M06.bmp';padding=128;scale=1.25;angle_step=2});
    scope='Four targeted causal checks, no threshold reduction or broad grid; single calls are not performance evidence'}}
if($Validate){$config=@{mode='expanded_scale_regression';threshold=75;levels=@(3);padding_left_top=128;
    padding_policy='Preflight every pose/refine level; min full extent=(template extent+16*T)*2^level; keep left/top128 and grow only right/bottom, align32. See actual_padding.json/padding_preflight.csv';
    scales=@(0..16 | ForEach-Object {.60+.05*$_});angle_step_degrees=2;templates=3060;opencv_threads=1;openmp_threads=4;
    source_image='M01.bmp';test_images=@('M02.bmp','M03.bmp','M04.bmp','M05.bmp','M06.bmp','M07.bmp');
    nms_iou=.3;match_iou=.5;scope='Fixed continuous scale .60..1.40 step .05, all seven images; no pose/scale GT; previously observed same-group regression';
    timing='One diagnostic call/image, no warmups, not performance evidence'}}
$config|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $OutputDirectory 'run_config.json') -Encoding UTF8
$sourceCopy=Join-Path $OutputDirectory 'source'
New-Item -ItemType Directory -Path $sourceCopy | Out-Null
foreach($name in @('magnet_demo.cpp','inspect_smd.py','evaluate.py','run.ps1')){
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $sourceCopy $name)
    if((Get-FileHash -LiteralPath (Join-Path $sourceCopy $name) -Algorithm SHA256).Hash -ne $before["artifacts/magnet_match/$name"]){throw 'Source snapshot SHA mismatch'}
}
$started=Get-Date -Format o
$argv=@('artifacts/magnet_match/build/input',$OutputDirectory)
if($Diagnose){$argv+='--diagnose'}
if($Validate){$argv+='--validate'}
& $exe @argv | Tee-Object -FilePath (Join-Path $OutputDirectory 'run.log')
$result=$LASTEXITCODE
foreach($path in $sources){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $before[$path]){throw "Source changed during run: $path"}}
foreach($path in $inputs.Keys){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $inputs[$path]){throw "Input changed during run: $path"}}
@{started_at=$started;completed_at=(Get-Date -Format o);exit_code=$result;source_sha256=$before;input_sha256=$inputs;
  compiler=$Compiler;flags=$flags;git_revision=((& git rev-parse HEAD).Trim());
  executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash;sources_unchanged=$true;inputs_unchanged=$true}|
  ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $OutputDirectory 'provenance.json') -Encoding UTF8
if($result -ne 0){throw "Magnet trial exited $result; preserve failed output"}
if($Validate){
    & py -3.10 artifacts/magnet_match/evaluate.py $OutputDirectory
    if($LASTEXITCODE -ne 0){throw 'Independent coarse localization audit failed'}
}
