param(
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$(Split-Path -Parent $Compiler);$OpenCV\build\bin;$env:PATH"
$protocol=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'COVERAGE_PROTOCOL.json') -Raw|ConvertFrom-Json
$publicBuild='artifacts/public_evaluation/build/build_manifest.json'
$manifest=Get-Content -LiteralPath $publicBuild -Raw|ConvertFrom-Json
if($manifest.core_git_revision -ne $protocol.core_revision){throw 'Coverage requires exact frozen core revision'}
$sources=[ordered]@{}
foreach($property in $manifest.source_sha256.PSObject.Properties){
    if((Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash -ne $property.Value){throw "Frozen public build source hash mismatch: $($property.Name)"}
    $sources[$property.Name]=$property.Value
}
if($sources['artifacts/public_evaluation/tless_eval.cpp'].ToLowerInvariant() -ne $protocol.adapter_sha256 -or $sources['artifacts/public_evaluation/eval_metrics.hpp'].ToLowerInvariant() -ne $protocol.metrics_sha256){throw 'Shared public adapter/metric recipe changed'}
foreach($dependency in (Get-ChildItem -LiteralPath MIPP -File -Recurse)){$sources[$dependency.FullName]=(Get-FileHash -LiteralPath $dependency.FullName -Algorithm SHA256).Hash}
foreach($name in @('coverage_eval.cpp','coverage_helper.hpp','coverage_nms.hpp','COVERAGE_PROTOCOL.json','build_eval.ps1','run_eval.ps1','verify_raw_provenance.py')){
    $path=Join-Path $PSScriptRoot $name;$sources[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
$sources[$publicBuild]=(Get-FileHash -LiteralPath $publicBuild -Algorithm SHA256).Hash
$core=@($sources.Keys|Where-Object {[IO.Path]::GetFileName($_) -eq 'line2Dup.cpp'})
if($core.Count -ne 1){throw 'Need one frozen core source'}
$flags=@('-std=c++17','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra','-Wno-sign-compare','-Wno-unused-function',"-I$(Split-Path -Parent $core[0])",'-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-I$OpenCV/modules/$module/include"}
$build=Join-Path $PSScriptRoot 'build';New-Item -ItemType Directory -Path $build -Force|Out-Null
$exe=Join-Path $build 'coverage_eval.exe'
& $Compiler @flags $core[0] (Join-Path $PSScriptRoot 'coverage_eval.cpp') "-L$OpenCV/build/lib" '-lopencv_world4120' '-lz' '-lbcrypt' '-o' $exe
if($LASTEXITCODE -ne 0){throw 'Coverage adapter build failed'}
foreach($path in $sources.Keys){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $sources[$path]){throw "Source changed during build: $path"}}
@{compiled_at=(Get-Date -Format o);core_revision=$protocol.core_revision;flags=$flags;compiler=$Compiler;source_sha256=$sources;
    public_build_manifest_sha256=$sources[$publicBuild];executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash;
    scope='Isolated frozen-recipe development coverage adapter; no matcher core changes or heldout mode'}|
    ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Encoding UTF8
Write-Output 'Coverage adapter build verified; no dataset images read'
