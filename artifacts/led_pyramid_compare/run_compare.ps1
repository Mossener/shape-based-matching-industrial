# Reproduce the two/three-level experiment with the installed local toolchain.
$ErrorActionPreference = 'Stop'
Push-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
try {
    $env:PATH = 'F:\mysys2\ucrt64\bin;D:\opencv-4.12.0\build\bin;' + $env:PATH
    $cvRoot = 'D:/opencv-4.12.0'
    $cvIncludes = @('-I.', '-IMIPP', "-I$cvRoot/build")
    foreach ($moduleName in @('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')) {
        $cvIncludes += "-I$cvRoot/modules/$moduleName/include"
    }
    $resultRoot = 'artifacts/led_pyramid_compare'
    foreach ($runName in @('L2_A', 'L3_A', 'L3_B', 'L2_B', 'paired')) {
        New-Item -ItemType Directory -Path "$resultRoot/$runName" -Force | Out-Null
    }
    & 'F:/mysys2/ucrt64/bin/g++.exe' -std=c++14 -O3 -mssse3 '-msse4.1' -fopenmp @cvIncludes line2Dup.cpp artifacts/led_match/led_demo.cpp '-LD:/opencv-4.12.0/build/lib' -lopencv_world4120 -o "$resultRoot/led_demo.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
    foreach ($runName in @('L2_A', 'L3_A', 'L3_B', 'L2_B')) {
        $levelCount = if ($runName.StartsWith('L2')) { 2 } else { 3 }
        & "$resultRoot/led_demo.exe" LED "$resultRoot/$runName" 7 $levelCount 1 > "$resultRoot/$runName/run.log"
        if ($LASTEXITCODE -ne 0) { throw "Failed run $runName" }
    }
    & "$resultRoot/led_demo.exe" --paired LED "$resultRoot/paired" > "$resultRoot/paired/run.log"
    if ($LASTEXITCODE -ne 0) { throw 'Paired benchmark failed' }
    & py -3.10 "$resultRoot/compare_results.py"
    if ($LASTEXITCODE -ne 0) { throw 'Comparison rendering failed' }
} finally { Pop-Location }
