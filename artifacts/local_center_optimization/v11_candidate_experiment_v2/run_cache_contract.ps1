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
& python (Join-Path $experiment 'prepare_sources.py') --mode verify
if($LASTEXITCODE -ne 0) {throw 'Frozen V11/V18 sources differ'}
$originsPath=Join-Path $experiment 'origins\manifest.json'
$origins=Get-Content -LiteralPath $originsPath -Raw | ConvertFrom-Json
$protected=[ordered]@{}
foreach($item in $origins.protected_source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $item.Name).Hash -ne $item.Value) {throw "Protected source differs: $($item.Name)"}
    $protected[$item.Name]=$item.Value
}
$test=Join-Path $experiment 'tests\direct_cache_contract.cpp'
$cache=Join-Path $experiment 'direct\line2Dup_local_cache.hpp'
$runtimePaths=@("$OpenCV/build/bin/libopencv_world4120.dll",
    (Join-Path (Split-Path -Parent $Compiler) 'libgomp-1.dll'),
    (Join-Path (Split-Path -Parent $Compiler) 'libstdc++-6.dll'),
    (Join-Path (Split-Path -Parent $Compiler) 'libgcc_s_seh-1.dll'))
$paths=@($PSCommandPath,$originsPath,(Join-Path $experiment 'prepare_sources.py'),$test,$cache,$Compiler)+$runtimePaths
foreach($relative in $origins.files.PSObject.Properties.Name) {$paths+=(Join-Path $experiment $relative)}
$pins=[ordered]@{}
foreach($path in $paths) {$pins[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$redPath=$null;$redHash=$null
if($Phase -eq 'Green') {
    if(-not $RedEvidence) {throw 'Green requires accepted literal -RedEvidence'}
    $redPath=(Resolve-Path -LiteralPath $RedEvidence).Path
    $redHash=(Get-FileHash -LiteralPath $redPath).Hash
    $red=Get-Content -LiteralPath $redPath -Raw | ConvertFrom-Json
    if($red.phase -ne 'Red' -or -not $red.accepted -or $red.compile_exit -ne 0 -or $red.test_exit -ne 1 -or
       $red.origins_manifest_sha256 -ne $pins[$originsPath] -or $red.test_source_sha256 -ne $pins[$test] -or
       -not (($red.test_output -join "`n").Contains('FAIL direct16 contract: stored result was not retrieved'))) {
        throw 'Valid behavioral RED with identical tests/frozen origins required'
    }
    $pins[$redPath]=$redHash
}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$build=Join-Path $experiment ('build\literal_'+$Phase.ToLower()+'_'+$stamp)
if(Test-Path -LiteralPath $build) {throw 'Literal build directory must be fresh'}
New-Item -ItemType Directory -Path $build | Out-Null
$exe=Join-Path $build 'direct_cache_contract.exe'
$json=Join-Path $experiment ('literal_'+$Phase.ToLower()+'_'+$stamp+'.json')
if(Test-Path -LiteralPath $json) {throw 'Literal evidence must be fresh'}
$env:PATH="$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$flags=@('-std=c++14','-O2','-Wall','-Wextra',"-I$OpenCV/build", "-I$OpenCV/modules/core/include",
    $test,"-L$OpenCV/build/lib",'-lopencv_world4120','-o',$exe)
$started=Get-Date -Format o
$ErrorActionPreference='Continue'
$compileOutput=@(& $Compiler @flags 2>&1 | ForEach-Object {"$_"});$compileExit=$LASTEXITCODE
$testOutput=@();$testExit=$null;$exeBefore=$null;$exeAfter=$null
if($compileExit -eq 0) {
    $exeBefore=(Get-FileHash -LiteralPath $exe).Hash
    $testOutput=@(& $exe 2>&1 | ForEach-Object {"$_"});$testExit=$LASTEXITCODE
    $exeAfter=if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe).Hash} else {$null}
}
$ErrorActionPreference='Stop'
$changes=@()
foreach($item in $pins.GetEnumerator()) {if((Get-FileHash -LiteralPath $item.Key).Hash -ne $item.Value) {$changes+=$item.Key}}
foreach($item in $protected.GetEnumerator()) {if((Get-FileHash -LiteralPath $item.Key).Hash -ne $item.Value) {$changes+=$item.Key}}
$expected=if($Phase -eq 'Red') {'FAIL direct16 contract: stored result was not retrieved'} else {'PASS direct16 contract:'}
$expectedExit=if($Phase -eq 'Red') {1} else {0}
$accepted=($compileExit -eq 0 -and $testExit -eq $expectedExit -and ($testOutput -join "`n").Contains($expected) -and
    $changes.Count -eq 0 -and $exeBefore -and $exeBefore -eq $exeAfter)
$result=[ordered]@{phase=$Phase;accepted=[bool]$accepted;started_at=$started;completed_at=(Get-Date -Format o);
    baseline_commit=$origins.baseline_commit;origins_manifest_sha256=$pins[$originsPath];test_source_sha256=$pins[$test];
    test_source_base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($test));
    cache_header_base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($cache));
    source_sha256=$pins;protected_source_sha256=$protected;source_changes_during_run=$changes;
    compiler=$Compiler;compiler_sha256=$pins[$Compiler];compiler_flags=$flags;runtime_paths=$runtimePaths;
    compile_exit=$compileExit;compile_output=$compileOutput;test_exit=$testExit;test_output=$testOutput;
    executable=$exe;executable_sha256_before=$exeBefore;executable_sha256_after=$exeAfter;executable_changed=($exeBefore -ne $exeAfter);
    red_evidence=$redPath;red_evidence_sha256=$redHash;
    limitation='Literal cache contract only; zero matcher executions/image decodes. No speed or accuracy claim.'}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $json -Encoding UTF8
$compileOutput | Write-Output;$testOutput | Write-Output;Write-Output "Evidence: $json"
if(-not $accepted) {throw "$Phase behavioral gate failed; original evidence retained"}
