param([string]$Output='artifacts/match_consolidation/unit_results.json')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH='D:\opencv-4.12.0\build\bin;F:\mysys2\ucrt64\bin;'+$env:PATH
$compiler='F:\mysys2\ucrt64\bin\g++.exe'
$build=Join-Path $PSScriptRoot 'build';New-Item -ItemType Directory -Path $build -Force|Out-Null
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP','-ID:/opencv-4.12.0/build')
foreach($m in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-ID:/opencv-4.12.0/modules/$m/include"}
$tests=@(@{name='match_consolidation';source='tests/match_consolidation_test.cpp'},
         @{name='local_accumulator_stress';source='tests/local_accumulator_stress_test.cpp'})
$sources=@('line2Dup.h','line2Dup_matches.hpp','line2Dup_local.hpp','line2Dup_search.hpp','tests/match_consolidation_test.cpp',
    'tests/local_accumulator_stress_test.cpp','artifacts/match_consolidation/run_unit_tests.ps1')
$hashes=[ordered]@{};foreach($p in $sources){$hashes[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash}
if(Test-Path -LiteralPath $Output){throw 'Choose a fresh unit result path'}
$results=@()
foreach($test in $tests){$exe=Join-Path $build ($test.name+'.exe')
    & $compiler @flags $test.source '-LD:/opencv-4.12.0/build/lib' '-lopencv_world4120' '-o' $exe
    if($LASTEXITCODE -ne 0){throw "Compile failed $($test.name)"}
    $text=& $exe 2>&1;$code=$LASTEXITCODE;$text|Write-Output
    $results+=@{name=$test.name;exit_code=$code;passed=($code -eq 0);output=($text -join "`n");executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash}
    foreach($p in $sources){if($hashes[$p] -ne (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash){throw "Source changed: $p"}}
    @{completed_at=(Get-Date -Format o);compiler=$compiler;compiler_flags=$flags;source_sha256=$hashes;tests=$results}|ConvertTo-Json -Depth 8|
        Set-Content -LiteralPath $Output -Encoding UTF8
    if($code -ne 0){throw "Test failed $($test.name)"}
}
