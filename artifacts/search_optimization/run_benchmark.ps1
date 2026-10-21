param(
    [switch]$Run,
    [switch]$Test,
    [switch]$SkipCompile,
    [int]$Repeats = 15,
    [int]$Warmups = 2,
    [string]$OutputDirectory = '',
    [string]$Compiler = 'F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV = 'D:\opencv-4.12.0'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH = "$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_NUM_THREADS='4'; $env:OMP_DYNAMIC='FALSE'; $env:OMP_MAX_ACTIVE_LEVELS='1'; $env:OMP_WAIT_POLICY='PASSIVE'
$build = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$executable = Join-Path $build 'search_benchmark.exe'
$testExecutable = Join-Path $build 'search_workspace_test.exe'
$kernelExecutable = Join-Path $build 'search_kernel_test.exe'
$flags = @('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) { $flags += "-I$OpenCV/modules/$module/include" }
$common = @('line2Dup.cpp','tests/search_reference_matcher.cpp')
$link = @("-L$OpenCV/build/lib",'-lopencv_world4120')
if(-not $SkipCompile) {
    & $Compiler @flags @common 'artifacts/search_optimization/benchmark.cpp' @link '-o' $executable
    if($LASTEXITCODE -ne 0) { throw 'Search benchmark compile failed' }
    & $Compiler @flags @common 'tests/search_workspace_test.cpp' @link '-o' $testExecutable
    if($LASTEXITCODE -ne 0) { throw 'Search workspace test compile failed' }
    & $Compiler @flags 'tests/search_kernel_test.cpp' @link '-o' $kernelExecutable
    if($LASTEXITCODE -ne 0) { throw 'Search kernel test compile failed' }
}
& $executable --describe
if($LASTEXITCODE -ne 0) { throw 'Search configuration smoke failed' }
& py -3.10 (Join-Path $PSScriptRoot 'summarize.py') --self-test
if($LASTEXITCODE -ne 0) { throw 'Search statistics self-test failed' }
$csvSmoke = & $executable --csv-smoke
if($LASTEXITCODE -ne 0) { throw 'CSV serializer smoke failed' }
$csvSmoke | & py -3.10 (Join-Path $PSScriptRoot 'summarize.py') --check-csv-layout
if($LASTEXITCODE -ne 0) { throw 'CSV field alignment failed' }
if($Test) {
    $testResults = @()
    $testSources = @('line2Dup.cpp','line2Dup.h','line2Dup_search.hpp',
        'tests/search_kernel_test.cpp','tests/search_workspace_test.cpp',
        'tests/search_reference_matcher.cpp','tests/search_reference_matcher.hpp',
        'artifacts/search_optimization/fixtures.hpp',
        'artifacts/search_optimization/baseline/line2Dup.cpp',
        'artifacts/search_optimization/baseline/line2Dup.h')
    $testHashes = @{}
    foreach($source in $testSources) { $testHashes[$source]=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
    foreach($testCase in @(
        @{name='search_kernel';executable=$kernelExecutable},
        @{name='search_workspace';executable=$testExecutable}
    )) {
        if(-not (Test-Path -LiteralPath $testCase.executable)) {
            throw "Missing test executable; compile without -SkipCompile: $($testCase.executable)"
        }
        $testOutput = & $testCase.executable 2>&1
        $testExit = $LASTEXITCODE
        $testOutput | Write-Output
        $testResults += @{test=$testCase.name;passed=($testExit -eq 0);exit_code=$testExit;
            output=($testOutput -join "`n");executable_sha256=(Get-FileHash -LiteralPath $testCase.executable -Algorithm SHA256).Hash}
        @{completed_at=(Get-Date -Format o);source_sha256=$testHashes;tests=$testResults;
            cv_threads=1;omp_wait_policy=$env:OMP_WAIT_POLICY;compiler=$Compiler;compiler_flags=$flags} |
            ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'search_test_results.json') -Encoding UTF8
        if($testExit -ne 0) { throw "Search correctness failed: $($testCase.name), exit=$testExit" }
    }
}
if(-not $Run) { Write-Output 'No performance measurement started; use -Run explicitly.'; return }
if($Repeats -lt 7 -or $Warmups -lt 1) { throw 'Need >=7 measured calls and >=1 warmup' }
if(-not $OutputDirectory) { $OutputDirectory=Join-Path $PSScriptRoot ('run_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath (Join-Path $output 'raw.csv')) { throw 'Choose a fresh output directory' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
$sources=@('line2Dup.cpp','line2Dup.h','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
    'tests/search_reference_matcher.cpp','tests/search_reference_matcher.hpp',
    'artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h',
    'artifacts/search_optimization/fixtures.hpp','artifacts/search_optimization/benchmark.cpp',
    'artifacts/search_optimization/summarize.py','artifacts/response_optimization/summarize.py',
    'artifacts/led_match/led_demo.cpp','LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png')
for($i=1;$i -le 8;$i++) { $sources += "LED/$i.bmp" }
$hashes=@{}; foreach($source in $sources) { $hashes[$source]=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
@{ started_at=(Get-Date -Format o); cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    compiler=$Compiler; compiler_version=((& $Compiler --version | Out-String).Trim()); compiler_flags=$flags;
    source_sha256=$hashes; git_head=((& git rev-parse HEAD | Out-String).Trim());
    cv_threads=1; omp_threads=4; omp_wait_policy=$env:OMP_WAIT_POLICY; omp_dynamic=$env:OMP_DYNAMIC;
    omp_max_active_levels=$env:OMP_MAX_ACTIVE_LEVELS; repeats=$Repeats; warmups=$Warmups } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'environment.json') -Encoding UTF8
& $executable --output $output --repeats $Repeats --warmups $Warmups 2>&1 | Tee-Object -FilePath (Join-Path $output 'run.log')
$benchmarkExit=$LASTEXITCODE
& py -3.10 (Join-Path $PSScriptRoot 'summarize.py') $output
$summaryExit=$LASTEXITCODE
if($benchmarkExit -ne 0 -or $summaryExit -ne 0) { throw "Search run failed benchmark=$benchmarkExit summary=$summaryExit" }
Write-Output "Results: $output"
