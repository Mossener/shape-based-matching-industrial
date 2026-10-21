param([switch]$Run,[string]$OutputDirectory='',[string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',[string]$OpenCV='D:\opencv-4.12.0')
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
Push-Location -LiteralPath $projectRoot
try {
    $env:PATH="$(Split-Path -Parent $Compiler);$OpenCV/build/bin;$env:PATH"
    $env:OMP_NUM_THREADS='4'; $env:OMP_DYNAMIC='FALSE'; $env:OMP_WAIT_POLICY='PASSIVE'; $env:OMP_MAX_ACTIVE_LEVELS='1'
    $build=Join-Path $PSScriptRoot 'build'
    New-Item -ItemType Directory -Path $build -Force | Out-Null
    $exe=Join-Path $build 'calibration.exe'
    $argsList=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP',"-I$OpenCV/build")
    foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {$argsList+="-I$OpenCV/modules/$module/include"}
    $argsList+=@('line2Dup.cpp','tests/reference_matcher.cpp','artifacts/search_optimization/calibration.cpp',"-L$OpenCV/build/lib",'-lopencv_world4120','-o',$exe)
    $old=$ErrorActionPreference; $ErrorActionPreference='Continue'
    & $Compiler @argsList *> (Join-Path $build 'calibration_build.log')
    $code=$LASTEXITCODE; $ErrorActionPreference=$old
    if($code -ne 0) {Get-Content (Join-Path $build 'calibration_build.log') -Tail 30; throw 'Calibration build failed'}
    & $exe --describe
    if($LASTEXITCODE -ne 0) {throw 'Calibration description failed'}
    if(!$Run) {Write-Output 'Compiled only. Use -Run after coordinating CPU availability.'; return}
    if(!$OutputDirectory) {$OutputDirectory=Join-Path $PSScriptRoot ('calibration_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))}
    if(Test-Path -LiteralPath (Join-Path $OutputDirectory 'raw.csv')) {throw 'Output already exists'}
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $paths=@('artifacts/search_optimization/calibration.cpp','tests/reference_matcher.cpp','tests/reference_matcher.hpp','artifacts/response_optimization/baseline/line2Dup.cpp','artifacts/response_optimization/baseline/line2Dup.h','artifacts/led_match/led_demo.cpp','test/case1/test_templ.yaml','test/case1/test.png','LED/ku.smd')
    1..8 | ForEach-Object {$paths+="LED/$_.bmp"}
    $hashes=@{}; foreach($path in $paths) {$hashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
    @{source_sha256=$hashes; compiler=(& $Compiler --version | Out-String); arguments=$argsList; started_at=(Get-Date -Format o)} | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $OutputDirectory 'environment.json')
    & $exe ([IO.Path]::GetFullPath($OutputDirectory))
    if($LASTEXITCODE -ne 0) {throw 'Calibration execution failed'}
} finally {Pop-Location}
