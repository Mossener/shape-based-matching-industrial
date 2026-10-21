param(
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$(Split-Path -Parent $Compiler);$OpenCV\build\bin;$env:PATH"
$build=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force|Out-Null
$check=Join-Path $build ('source_check_'+(Get-Date -Format 'yyyyMMdd_HHmmss_ffff')+'.json')
& py -3.10 (Join-Path $PSScriptRoot 'verify_inputs.py') --check-protocol --output $check
if($LASTEXITCODE -ne 0){throw 'Frozen source/protocol audit failed; no compilation'}
$publicBuild='artifacts/public_evaluation/build/build_manifest.json'
$public=Get-Content -LiteralPath $publicBuild -Raw|ConvertFrom-Json
$sources=[ordered]@{}
foreach($property in $public.source_sha256.PSObject.Properties){$sources[$property.Name]=$property.Value}
foreach($file in (Get-ChildItem -LiteralPath MIPP -File -Recurse)){$sources[$file.FullName]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
foreach($name in @('padding_plan.hpp','padding_plan_test.cpp','padding_eval.cpp','PROTOCOL.json','frame_schedule.json','preflight_plan.json','verify_inputs.py','build_eval.ps1','run_eval.ps1','run_planner_tests.py')){
    $path=Join-Path $PSScriptRoot $name;$sources[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
foreach($path in @($publicBuild,'artifacts/quality_coverage/verify_raw_provenance.py','artifacts/quality_coverage/COVERAGE_PROTOCOL.json')){$sources[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$core=@($sources.Keys|Where-Object {[IO.Path]::GetFileName($_) -eq 'line2Dup.cpp'})
if($core.Count -ne 1){throw 'Need one frozen V11 core source'}
$flags=@('-std=c++17','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra','-Wno-sign-compare','-Wno-unused-function',"-I$(Split-Path -Parent $core[0])",'-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-I$OpenCV/modules/$module/include"}
$exe=Join-Path $build 'padding_eval.exe'
& $Compiler @flags $core[0] (Join-Path $PSScriptRoot 'padding_eval.cpp') "-L$OpenCV/build/lib" '-lopencv_world4120' '-lz' '-lpsapi' '-o' $exe
if($LASTEXITCODE -ne 0){throw 'Padding adapter build failed; retain compiler output'}
foreach($path in $sources.Keys){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $sources[$path]){throw "Source changed during build: $path"}}
@{compiled_at=(Get-Date -Format o);core_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed';compiler=$Compiler;flags=$flags;source_sha256=$sources;executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash;scope='Isolated fixed obj8 full-bank padding adapter; no core/public source changes'}|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Encoding UTF8
