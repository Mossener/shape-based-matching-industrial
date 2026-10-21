param(
    [Parameter(Mandatory=$true)][ValidateSet('Red','Green')][string]$Phase,
    [string]$RedEvidence='',
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
$experiment=[IO.Path]::GetFullPath($PSScriptRoot)
$root=[IO.Path]::GetFullPath((Join-Path $experiment '..\..\..'))
Set-Location -LiteralPath $root
& python (Join-Path $experiment 'snapshot_v11.py') --mode verify
if($LASTEXITCODE -ne 0) {throw 'Frozen V11 snapshot verification failed'}
$test=Join-Path $experiment 'tests\cache_contract_test.cpp'
$stub=Join-Path $experiment 'candidate\line2Dup_local_cache.hpp'
$baselineManifest=Join-Path $experiment 'baseline\manifest.json'
$baseline=Get-Content -LiteralPath $baselineManifest -Raw | ConvertFrom-Json
$protected=@($baseline.files.PSObject.Properties.Name)+@(
    'line2Dup_local_cache.hpp','tests/local_center_cache_test.cpp',
    'tests/local_center_workspace_test.cpp',
    'docs/superpowers/plans/2026-10-21-local-center-cache.md')
$protectedHashes=[ordered]@{}
foreach($path in $protected) {$protectedHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$sources=@($test,$stub,$baselineManifest,(Join-Path $experiment 'snapshot_v11.py'),$PSCommandPath)
foreach($name in $baseline.files.PSObject.Properties.Name) {$sources+=Join-Path $experiment ('baseline\'+$name)}
foreach($name in $baseline.core_files) {$sources+=Join-Path $experiment ('candidate\'+$name)}
$hashes=[ordered]@{}
foreach($path in $sources) {$hashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
if($Phase -eq 'Green') {
    if(-not $RedEvidence) {throw 'Green requires -RedEvidence pointing to accepted behavioral RED'}
    $red=Get-Content -LiteralPath $RedEvidence -Raw | ConvertFrom-Json
    if($red.phase -ne 'Red' -or -not $red.accepted -or $red.compile_exit -ne 0 -or $red.test_exit -ne 1) {throw 'Invalid RED evidence'}
    if($red.test_source_sha256 -ne $hashes[$test] -or $red.baseline_manifest_sha256 -ne $hashes[$baselineManifest]) {throw 'Tests or baseline changed since RED'}
}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$build=Join-Path $experiment ('build\cache_contract_'+$Phase.ToLower()+'_'+$stamp)
if(Test-Path -LiteralPath $build) {throw 'Choose a fresh build directory'}
New-Item -ItemType Directory -Path $build | Out-Null
$exe=Join-Path $build 'cache_contract.exe'
$output=Join-Path $experiment ('cache_contract_'+$Phase.ToLower()+'_'+$stamp+'.json')
$env:PATH="$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$flags=@('-std=c++14','-O2','-Wall','-Wextra',"-I$OpenCV/build", "-I$OpenCV/modules/core/include",$test,"-L$OpenCV/build/lib",'-lopencv_world4120','-o',$exe)
$started=Get-Date -Format o
$ErrorActionPreference='Continue'
$compileOutput=@(& $Compiler @flags 2>&1 | ForEach-Object {"$_"})
$compileExit=$LASTEXITCODE
$testOutput=@();$testExit=$null
if($compileExit -eq 0) {$testOutput=@(& $exe 2>&1 | ForEach-Object {"$_"});$testExit=$LASTEXITCODE}
$ErrorActionPreference='Stop'
$changes=@()
foreach($path in $sources) {if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $hashes[$path]) {$changes+=$path}}
foreach($path in $protected) {if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $protectedHashes[$path]) {$changes+=$path}}
$expected=if($Phase -eq 'Red') {'FAIL cache contract: stored result was not retrieved'} else {'PASS cache contract:'}
$expectedExit=if($Phase -eq 'Red') {1} else {0}
$accepted=($compileExit -eq 0 -and $testExit -eq $expectedExit -and ($testOutput -join "`n").Contains($expected) -and $changes.Count -eq 0)
$result=[ordered]@{phase=$Phase;accepted=$accepted;started_at=$started;completed_at=(Get-Date -Format o);
    baseline_commit=$baseline.commit;baseline_manifest_sha256=$hashes[$baselineManifest];test_source_sha256=$hashes[$test];
    test_source_base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($test));
    cache_header_base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($stub));
    source_sha256=$hashes;protected_source_sha256=$protectedHashes;source_changes_during_run=$changes;
    compiler=$Compiler;compiler_sha256=(Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash;
    compiler_flags=$flags;compile_exit=$compileExit;compile_output=$compileOutput;
    test_exit=$testExit;test_output=$testOutput;executable=$exe;executable_sha256=$(if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash} else {$null});
    red_evidence=$RedEvidence;limitation='Literal cache contract only. No matcher compilation, matching, speed or accuracy claim.'}
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $output -Encoding UTF8
$compileOutput | Write-Output
$testOutput | Write-Output
Write-Output "Evidence: $output"
if(-not $accepted) {throw "$Phase behavioral gate failed; evidence retained"}
