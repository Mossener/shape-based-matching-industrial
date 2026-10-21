param(
    [switch]$Run,
    [switch]$ValidateOnly,
    [switch]$SkipCompile,
    [switch]$RefreshSnapshot,
    [int]$Repeats=7,
    [int]$Warmups=2,
    [string]$Dataset='',
    [string]$Image='',
    [string]$OutputDirectory='',
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
$manifestFile=Join-Path $PSScriptRoot 'source_manifest.json'
if($RefreshSnapshot -or -not (Test-Path -LiteralPath $manifestFile)) {
    if($SkipCompile) {throw 'Snapshot refresh requires compilation'}
    & py -3.10 (Join-Path $PSScriptRoot 'generate_profile.py')
    if($LASTEXITCODE -ne 0) {throw 'Snapshot generation failed'}
}
$manifest=Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
foreach($entry in $manifest.source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Production source drift: $($entry.Name); refresh intentionally with -RefreshSnapshot"
    }
}
foreach($entry in $manifest.generated_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Generated source drift: $($entry.Name)"
    }
}
$build=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$executable=Join-Path $build 'search_profile.exe'
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {$flags+="-I$OpenCV/modules/$module/include"}
if(-not $SkipCompile) {
    & $Compiler @flags 'line2Dup.cpp' 'tests/search_reference_matcher.cpp' 'artifacts/search_profile/source/line2Dup.cpp' 'artifacts/search_profile/profile.cpp' "-L$OpenCV/build/lib" '-lopencv_world4120' '-o' $executable
    if($LASTEXITCODE -ne 0) {throw 'Profile compile failed'}
    $buildHashes=@{}
    foreach($path in @('line2Dup.cpp','line2Dup.h','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
        'artifacts/search_profile/profile.cpp','artifacts/search_profile/profile.hpp','artifacts/search_profile/source_manifest.json',
        'artifacts/search_optimization/fixtures.hpp','artifacts/led_match/led_demo.cpp',
        'tests/search_reference_matcher.cpp','tests/search_reference_matcher.hpp',
        'artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h')) {
        $buildHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    @{compiler=$Compiler;flags=$flags;source_sha256=$buildHashes;executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Encoding UTF8
}
$buildManifest=Get-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Raw | ConvertFrom-Json
foreach($entry in $buildManifest.source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash -ne $entry.Value) {
        throw "Build source drift: $($entry.Name); compile without -SkipCompile"
    }
}
if((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $buildManifest.executable_sha256) {throw 'Executable hash differs from its build manifest'}
& $executable --describe
if($LASTEXITCODE -ne 0) {throw 'Profile description smoke failed'}
if(-not $Run -and -not $ValidateOnly) {Write-Output 'Compiled only; coordinate the CPU slot before -Run or -ValidateOnly.';return}
if($Repeats -lt 1 -or $Warmups -lt 0) {throw 'Need repeats>=1, warmups>=0'}
if(-not $OutputDirectory) {$OutputDirectory=Join-Path $PSScriptRoot ('run_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))}
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath (Join-Path $output 'validation.csv')) {throw 'Choose a fresh output directory'}
New-Item -ItemType Directory -Path $output -Force | Out-Null
$hashes=@{}
$sources=@('line2Dup.cpp','line2Dup.h','line2Dup_search.hpp','line2Dup_spread.hpp','line2Dup_response.hpp',
    'artifacts/search_profile/profile.cpp','artifacts/search_profile/profile.hpp','artifacts/search_profile/source_manifest.json',
    'artifacts/search_profile/generate_profile.py','artifacts/search_optimization/fixtures.hpp','artifacts/led_match/led_demo.cpp',
    'LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png')
for($i=1;$i -le 8;$i++) {$sources+="LED/$i.bmp"}
foreach($path in $sources) {$hashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
@{started_at=(Get-Date -Format o);git_head=((& git rev-parse HEAD | Out-String).Trim());source_sha256=$hashes;
    executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash;compiler=$Compiler;compiler_flags=$flags;
    compiler_version=((& $Compiler --version | Out-String).Trim());cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    cv_threads=1;omp_threads=4;omp_wait_policy=$env:OMP_WAIT_POLICY;repeats=$Repeats;warmups=$Warmups;dataset=$Dataset;image=$Image;
    timer_note='Per-template elapsed worker intervals summed across workers are not wall time or process CPU time; profiler overhead perturbs execution'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'environment.json') -Encoding UTF8
$arguments=@('--output',$output,'--repeats',"$Repeats",'--warmups',"$Warmups")
if($Dataset) {$arguments+=@('--dataset',$Dataset)}
if($Image) {$arguments+=@('--image',$Image)}
if($ValidateOnly) {$arguments+='--validate-only'}
& $executable @arguments 2>&1 | Tee-Object -FilePath (Join-Path $output 'run.log')
if($LASTEXITCODE -ne 0) {throw 'Profile correctness or collection failed'}
if(-not $ValidateOnly) {
    & py -3.10 (Join-Path $PSScriptRoot 'summarize.py') $output
    if($LASTEXITCODE -ne 0) {throw 'Profile summary failed'}
}
Write-Output "Results: $output"
