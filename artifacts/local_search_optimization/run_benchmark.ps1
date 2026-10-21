param(
    [switch]$Run,
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
$executable = Join-Path $build 'local_search_benchmark.exe'
$manifest = Join-Path $build 'build_manifest.json'
$flags = @('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) { $flags += "-I$OpenCV/modules/$module/include" }
$sources = @('line2Dup.cpp','line2Dup.h','line2Dup_local.hpp','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
    'tests/search_reference_matcher.cpp','tests/search_reference_matcher.hpp',
    'artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h',
    'artifacts/search_optimization/fixtures.hpp','artifacts/led_match/led_demo.cpp',
    'artifacts/local_search_optimization/benchmark.cpp','artifacts/local_search_optimization/run_benchmark.ps1',
    'artifacts/local_search_optimization/summarize.py')
function Get-SourceHashes {
    $result = [ordered]@{}
    foreach($source in $sources) { $result[$source] = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
    return $result
}
function Assert-HashesEqual($before, $after, $context) {
    foreach($source in $sources) {
        if($before[$source] -ne $after[$source]) { throw "Source changed $context : $source" }
    }
}
$compiledHashes = Get-SourceHashes
if(-not $SkipCompile) {
    & $Compiler @flags 'line2Dup.cpp' 'tests/search_reference_matcher.cpp' 'artifacts/local_search_optimization/benchmark.cpp' "-L$OpenCV/build/lib" '-lopencv_world4120' '-o' $executable
    if($LASTEXITCODE -ne 0) { throw 'Local search benchmark compile failed' }
    Assert-HashesEqual $compiledHashes (Get-SourceHashes) 'during compilation'
    @{compiled_at=(Get-Date -Format o);source_sha256=$compiledHashes;compiler=$Compiler;compiler_flags=$flags;
      executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifest -Encoding UTF8
} else {
    if(-not (Test-Path -LiteralPath $manifest)) { throw 'Missing build manifest; compile first' }
    $saved = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $savedHashes = @{}
    foreach($property in $saved.source_sha256.PSObject.Properties) { $savedHashes[$property.Name] = $property.Value }
    Assert-HashesEqual $savedHashes $compiledHashes 'since compilation; rebuild before running'
    if($saved.executable_sha256 -ne (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash) {
        throw 'Executable hash differs from build manifest'
    }
}
& $executable --describe
if($LASTEXITCODE -ne 0) { throw 'Local search configuration smoke failed' }
& py -3.10 (Join-Path $PSScriptRoot 'summarize.py') --self-test
if($LASTEXITCODE -ne 0) { throw 'Local search summary self-test failed' }
$csvSmoke = & $executable --csv-smoke
if($LASTEXITCODE -ne 0) { throw 'Local search CSV smoke failed' }
$csvSmoke | & py -3.10 (Join-Path $PSScriptRoot 'summarize.py') --check-csv-layout
if($LASTEXITCODE -ne 0) { throw 'Local search CSV layout failed' }
if(-not $Run) { Write-Output 'Compiled and smoke-checked. No matching/performance measurement started; coordinate CPU before using -Run.'; return }
if($Repeats -lt 7 -or $Warmups -lt 1) { throw 'Need >=7 measured calls and >=1 warmup' }
if(-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot ('run_' + (Get-Date -Format 'yyyyMMdd_HHmmss')) }
$output = [IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output) { throw 'Choose a fresh output directory' }
New-Item -ItemType Directory -Path $output | Out-Null
$inputSources = @('LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png')
for($i=1;$i -le 8;$i++) { $inputSources += "LED/$i.bmp" }
$inputHashes = [ordered]@{}
foreach($source in $inputSources) { $inputHashes[$source] = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash }
@{started_at=(Get-Date -Format o);source_sha256=$compiledHashes;input_sha256=$inputHashes;
  executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash;
  cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
  compiler=$Compiler;compiler_version=((& $Compiler --version | Out-String).Trim());compiler_flags=$flags;
  git_head=((& git rev-parse HEAD | Out-String).Trim());cv_threads=1;omp_threads=4;
  omp_dynamic=$env:OMP_DYNAMIC;omp_wait_policy=$env:OMP_WAIT_POLICY;omp_max_active_levels=$env:OMP_MAX_ACTIVE_LEVELS;
  repeats=$Repeats;warmups=$Warmups} | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $output 'environment.json') -Encoding UTF8
& $executable --output $output --repeats $Repeats --warmups $Warmups 2>&1 |
    Tee-Object -FilePath (Join-Path $output 'run.log')
$benchmarkExit = $LASTEXITCODE
Assert-HashesEqual $compiledHashes (Get-SourceHashes) 'during measurement'
& py -3.10 (Join-Path $PSScriptRoot 'summarize.py') $output
$summaryExit = $LASTEXITCODE
@{completed_at=(Get-Date -Format o);benchmark_exit=$benchmarkExit;summary_exit=$summaryExit;
  sources_unchanged=$true} | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $output 'completion.json') -Encoding UTF8
if($benchmarkExit -ne 0 -or $summaryExit -ne 0) { throw "Local search failed benchmark=$benchmarkExit summary=$summaryExit" }
Write-Output "Results: $output"
