param(
    [string]$Compiler = 'F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV = 'D:\opencv-4.12.0',
    [string]$OutputFile = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH = "$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_WAIT_POLICY='PASSIVE'; $env:OMP_DYNAMIC='FALSE'; $env:OMP_MAX_ACTIVE_LEVELS='1'
$build = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$flags = @('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP',"-I$OpenCV/build")
foreach ($module in @('core','imgproc','highgui','imgcodecs','videoio')) { $flags += "-I$OpenCV/modules/$module/include" }
$link = @("-L$OpenCV/build/lib",'-lopencv_world4120')
$cases = @(
    @{name='local_accumulator'; source='tests/local_accumulator_test.cpp'; extra=@()},
    @{name='local_search_workspace'; source='tests/local_search_workspace_test.cpp'; extra=@('tests/search_reference_matcher.cpp')}
)
$sources = @('line2Dup.cpp','line2Dup.h','line2Dup_local.hpp','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
    'tests/local_accumulator_test.cpp','tests/local_search_workspace_test.cpp','tests/search_reference_matcher.cpp',
    'tests/search_reference_matcher.hpp','artifacts/search_optimization/fixtures.hpp','artifacts/led_match/led_demo.cpp',
    'artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h')
$hashes = [ordered]@{}
foreach ($source in $sources) { $hashes[$source]=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
if (-not $OutputFile) { $OutputFile = Join-Path $PSScriptRoot ('tests_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json') }
if (Test-Path -LiteralPath $OutputFile) { throw 'Choose a fresh result file' }
$results = @()
foreach ($case in $cases) {
    $exe = Join-Path $build ($case.name+'.exe')
    & $Compiler @flags $case.source @($case.extra) @link '-o' $exe
    if ($LASTEXITCODE -ne 0) { throw "Compile failed: $($case.name)" }
    $output = & $exe 2>&1
    $exit = $LASTEXITCODE
    $output | Write-Output
    $results += @{name=$case.name;exit_code=$exit;passed=($exit -eq 0);output=($output -join "`n");
        executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash}
    foreach ($source in $sources) {
        if ($hashes[$source] -ne (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash) { throw "Source changed: $source" }
    }
    @{completed_at=(Get-Date -Format o);source_sha256=$hashes;compiler=$Compiler;compiler_flags=$flags;
        cv_threads=1;omp_thread_matrix=@(1,4,2,4);omp_wait_policy=$env:OMP_WAIT_POLICY;tests=$results} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
    if ($exit -ne 0) { throw "Test failed: $($case.name)" }
}
