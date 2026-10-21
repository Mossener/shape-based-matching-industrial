param(
    [switch]$Run,
    [int]$Repeats = 7,
    [int]$Warmups = 1,
    [string]$OutputDirectory = '',
    [string]$Compiler = 'F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV = 'D:\opencv-4.12.0',
    [string]$Python = 'py',
    [string[]]$PythonArguments = @('-3.10')
)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Set-Location -LiteralPath $workspace
$env:PATH = "$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_NUM_THREADS = '4'
$env:OMP_DYNAMIC = 'FALSE'
$env:OMP_MAX_ACTIVE_LEVELS = '1'
$env:OMP_WAIT_POLICY = 'PASSIVE'
$buildDirectory = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$executable = Join-Path $buildDirectory 'response_benchmark.exe'
$arguments = @('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {
    $arguments += "-I$OpenCV/modules/$module/include"
}
$arguments += @('line2Dup.cpp','tests/reference_matcher.cpp','artifacts/response_optimization/benchmark.cpp',"-L$OpenCV/build/lib",'-lopencv_world4120','-o',$executable)
& $Compiler @arguments
if($LASTEXITCODE -ne 0) { throw "Benchmark compilation failed: $LASTEXITCODE" }
& $executable --describe
if($LASTEXITCODE -ne 0) { throw 'Benchmark configuration smoke check failed' }
& $Python @PythonArguments (Join-Path $PSScriptRoot 'summarize.py') --self-test
if($LASTEXITCODE -ne 0) { throw 'Statistics self-test failed' }
$csvSmoke = & $executable --csv-smoke
if($LASTEXITCODE -ne 0) { throw 'CSV smoke serializer failed' }
$csvSmoke | & $Python @PythonArguments (Join-Path $PSScriptRoot 'summarize.py') --check-csv-layout
if($LASTEXITCODE -ne 0) { throw 'Original/current CSV field layout check failed' }
if(-not $Run) {
    Write-Output 'Compiled and smoke-checked only. Use -Run to start the benchmark.'
    return
}
if($Repeats -lt 7 -or $Warmups -lt 1) { throw 'Use at least seven measured calls and one warmup' }
if(-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot ('run_' + (Get-Date -Format 'yyyyMMdd_HHmmss')) }
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath (Join-Path $resolvedOutput 'raw.csv')) { throw 'Output already contains raw.csv; choose a fresh directory' }
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$sources = @('line2Dup.cpp','line2Dup.h','line2Dup_response.hpp','line2Dup_spread.hpp',
    'tests/reference_matcher.cpp','tests/reference_matcher.hpp','artifacts/led_match/led_demo.cpp',
    'artifacts/response_optimization/baseline/line2Dup.cpp','artifacts/response_optimization/baseline/line2Dup.h',
    'artifacts/response_optimization/benchmark.cpp','LED/ku.smd')
$hashes = @{}
foreach($source in $sources) { $hashes[$source] = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
for($image=1;$image -le 8;$image++) { $source="LED/$image.bmp"; $hashes[$source]=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
$system = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
$compilerVersion = (& $Compiler --version | Out-String).Trim()
@{ started_at=(Get-Date -Format o); compiler=$Compiler; compiler_version=$compilerVersion;
    compile_arguments=$arguments; cpu=$system; source_sha256=$hashes;
    python=$Python; python_arguments=$PythonArguments;
    runtime_environment=@{OMP_NUM_THREADS=$env:OMP_NUM_THREADS;OMP_DYNAMIC=$env:OMP_DYNAMIC;
        OMP_MAX_ACTIVE_LEVELS=$env:OMP_MAX_ACTIVE_LEVELS;OMP_WAIT_POLICY=$env:OMP_WAIT_POLICY};
    opencv=$OpenCV; process_id=$PID; power_policy='inherited; no system power settings changed' } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $resolvedOutput 'environment.json') -Encoding UTF8
& $executable --input LED --output $resolvedOutput --repeats $Repeats --warmups $Warmups 2>&1 |
    Tee-Object -FilePath (Join-Path $resolvedOutput 'run.log')
$benchmarkExit = $LASTEXITCODE
& $Python @PythonArguments (Join-Path $PSScriptRoot 'summarize.py') $resolvedOutput
$summaryExit = $LASTEXITCODE
if($benchmarkExit -ne 0 -or $summaryExit -ne 0) { throw "Validation failed: benchmark=$benchmarkExit summary=$summaryExit" }
Write-Output "Results: $resolvedOutput"
