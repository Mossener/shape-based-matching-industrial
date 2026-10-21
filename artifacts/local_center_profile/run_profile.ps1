param(
    [switch]$Run,
    [switch]$SkipCompile,
    [string]$OutputDirectory='',
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
$manifestPath=Join-Path $PSScriptRoot 'source_manifest.json'
if(-not (Test-Path -LiteralPath $manifestPath)) {
    if($SkipCompile) {throw 'Compile the census first'}
    & py -3.10 (Join-Path $PSScriptRoot 'generate_profile.py')
    if($LASTEXITCODE -ne 0) {throw 'Center census source generation failed'}
}
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach($entry in $manifest.generated_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Center diagnostic source drift: $($entry.Name)"
    }
}
$build=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$executable=Join-Path $build 'local_centers.exe'
$flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wno-sign-compare','-I.','-IMIPP',"-I$OpenCV/build")
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {$flags+="-I$OpenCV/modules/$module/include"}
$sources=@('artifacts/local_center_profile/centers.cpp','artifacts/local_center_profile/profile.hpp','artifacts/local_center_profile/source_manifest.json',
    'artifacts/local_center_profile/fixtures_v9.hpp','artifacts/led_match/led_demo.cpp','tests/search_reference_matcher.cpp',
    'tests/search_reference_matcher.hpp','artifacts/search_optimization/baseline/line2Dup.cpp','artifacts/search_optimization/baseline/line2Dup.h')
if(-not $SkipCompile) {
    & $Compiler @flags 'tests/search_reference_matcher.cpp' 'artifacts/local_center_profile/source/line2Dup.cpp' 'artifacts/local_center_profile/centers.cpp' "-L$OpenCV/build/lib" '-lopencv_world4120' '-o' $executable
    if($LASTEXITCODE -ne 0) {throw 'Center census compile failed'}
    $buildHashes=@{};foreach($path in $sources) {$buildHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
    @{compiler=$Compiler;flags=$flags;source_sha256=$buildHashes;executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Encoding UTF8
}
$built=Get-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Raw | ConvertFrom-Json
foreach($entry in $built.source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash -ne $entry.Value) {throw "Build source drift: $($entry.Name)"}
}
if((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $built.executable_sha256) {throw 'Center executable hash differs from build'}
& $executable --describe
if($LASTEXITCODE -ne 0) {throw 'Center description smoke failed'}
if(-not $Run) {Write-Output 'Compiled only; coordinate exclusive CPU use before -Run.';return}
if(-not $OutputDirectory) {$OutputDirectory=Join-Path $PSScriptRoot ('run_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))}
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath (Join-Path $output 'validation.csv')) {throw 'Choose a fresh output directory'}
New-Item -ItemType Directory -Path $output -Force | Out-Null
$hashes=@{};$inputs=@('LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png')
for($i=1;$i -le 8;$i++) {$inputs+="LED/$i.bmp"}
foreach($path in ($sources+$inputs)) {$hashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
@{started_at=(Get-Date -Format o);base_snapshot_git_head=$manifest.base_git_head;source_sha256=$hashes;
    executable_sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash;compiler=$Compiler;compiler_flags=$flags;
    compiler_version=((& $Compiler --version | Out-String).Trim());cv_threads=1;omp_threads=4;omp_wait_policy=$env:OMP_WAIT_POLICY;
    calls_per_image=@{V4=1;instrumented=1};timing='count-only census, no speed conclusion'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'environment.json') -Encoding UTF8
& $executable --output $output 2>&1 | Tee-Object -FilePath (Join-Path $output 'run.log')
if($LASTEXITCODE -ne 0) {throw 'Center census or V4 correctness failed'}
& py -3.10 (Join-Path $PSScriptRoot 'summarize.py') $output
if($LASTEXITCODE -ne 0) {throw 'Center summary/audit failed'}
Write-Output "Results: $output"
