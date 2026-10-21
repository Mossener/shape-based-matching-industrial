$ErrorActionPreference = 'Stop'
Push-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
try {
    $env:PATH = 'F:\mysys2\ucrt64\bin;D:\opencv-4.12.0\build\bin;' + $env:PATH
    $cvRoot = 'D:/opencv-4.12.0'
    $cvIncludes = @('-I.', '-IMIPP', "-I$cvRoot/build")
    foreach ($moduleName in @('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')) {
        $cvIncludes += "-I$cvRoot/modules/$moduleName/include"
    }
    & 'F:/mysys2/ucrt64/bin/g++.exe' -std=c++14 -O3 -mssse3 '-msse4.1' -fopenmp @cvIncludes line2Dup.cpp artifacts/led_match/led_demo.cpp '-LD:/opencv-4.12.0/build/lib' -lopencv_world4120 -o artifacts/led_match/led_demo.exe
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
    & artifacts/led_match/led_demo.exe LED artifacts/led_match 5 > artifacts/led_match/run.log
    if ($LASTEXITCODE -ne 0) { throw 'LED matching failed' }
    & py -3.10 artifacts/led_match/render_results.py
    if ($LASTEXITCODE -ne 0) { throw 'Result rendering failed' }
} finally { Pop-Location }
