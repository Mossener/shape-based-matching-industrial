param(
    [Parameter(Mandatory=$true)][ValidateSet('Build','Run')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$GreenEvidence,
    [ValidateSet('core','flags','lifetime','all')][string]$Stage='core',
    [string]$BuildDirectory='',
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
$experiment=[IO.Path]::GetFullPath($PSScriptRoot)
$root=[IO.Path]::GetFullPath((Join-Path $experiment '..\..\..'))
Set-Location -LiteralPath $root
$env:PATH="$OpenCV\build\bin;$(Split-Path -Parent $Compiler);$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
& python (Join-Path $experiment 'snapshot_v11.py') --mode verify
if($LASTEXITCODE -ne 0) {throw 'Frozen V11 bytes differ'}
$greenPath=(Resolve-Path -LiteralPath $GreenEvidence).Path
$green=Get-Content -LiteralPath $greenPath -Raw | ConvertFrom-Json
if($green.phase -ne 'Green' -or -not $green.accepted -or $green.compile_exit -ne 0 -or $green.test_exit -ne 0) {throw 'Accepted cache GREEN evidence required'}
$cache=Join-Path $experiment 'candidate\line2Dup_local_cache.hpp'
$cacheBytes=[IO.File]::ReadAllBytes($cache)
$savedCache=[Convert]::FromBase64String($green.cache_header_base64)
if([Convert]::ToBase64String($cacheBytes) -ne [Convert]::ToBase64String($savedCache)) {throw 'Cache header changed since GREEN'}
$cacheTest=Join-Path $experiment 'tests\cache_contract_test.cpp'
if((Get-FileHash -LiteralPath $cacheTest).Hash -ne $green.test_source_sha256) {throw 'Literal contract tests changed since GREEN'}
$baselinePath=Join-Path $experiment 'baseline\manifest.json'
if((Get-FileHash -LiteralPath $baselinePath -Algorithm SHA256).Hash -ne $green.baseline_manifest_sha256) {throw 'Baseline changed since GREEN'}
$baseline=Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
foreach($name in @('line2Dup_local.hpp','line2Dup_search.hpp','line2Dup_response.hpp','line2Dup_spread.hpp','line2Dup_matches.hpp')) {
    if((Get-FileHash -LiteralPath (Join-Path $experiment ('candidate\'+$name))).Hash -ne (Get-FileHash -LiteralPath (Join-Path $experiment ('baseline\'+$name))).Hash) {throw "Unrelated candidate header changed: $name"}
}
$paths=@($PSCommandPath,$greenPath,$baselinePath,(Join-Path $experiment 'snapshot_v11.py'),
    (Join-Path $experiment 'candidate_initial_manifest.json'),(Join-Path $experiment 'REGRESSION_MATRIX.json'),
    (Join-Path $experiment 'v11_reference.hpp'),(Join-Path $experiment 'v11_reference.cpp'),
    (Join-Path $experiment 'tests\matcher_contract_test.cpp'),$cache,$cacheTest,
    'artifacts/led_match/led_demo.cpp','LED/ku.smd','test/case1/test_templ.yaml','test/case1/test.png',
    'datasets/tless_train_f32/templates_tless_object_1.yml.gz','datasets/tless_tiny/index.json')
foreach($name in $baseline.files.PSObject.Properties.Name) {$paths+=(Join-Path $experiment ('baseline\'+$name))}
foreach($name in $baseline.core_files) {$paths+=(Join-Path $experiment ('candidate\'+$name))}
for($i=1;$i -le 8;++$i) {$paths+="LED/$i.bmp"}
$index=Get-Content -LiteralPath 'datasets/tless_tiny/index.json' -Raw | ConvertFrom-Json
$development=@($index.test | Where-Object {$_.split -eq 'development'})
if($development.Count -ne 16) {throw 'Expected exactly sixteen tiny development frames'}
foreach($frame in $development) {$paths+=(Join-Path 'datasets/tless_tiny' $frame.rgb)}
$hashes=[ordered]@{}
foreach($path in $paths) {$hashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$protected=@($baseline.files.PSObject.Properties.Name)+@('line2Dup_local_cache.hpp',
    'tests/local_center_cache_test.cpp','tests/local_center_workspace_test.cpp',
    'docs/superpowers/plans/2026-10-21-local-center-cache.md',
    'artifacts/local_center_optimization/baseline/manifest.json')
$protectedHashes=[ordered]@{}
foreach($path in $protected) {$protectedHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
if($Mode -eq 'Build') {
    if(-not $BuildDirectory) {$BuildDirectory=Join-Path $experiment ('build\matcher_'+$stamp)}
    $build=[IO.Path]::GetFullPath($BuildDirectory)
    $allowed=[IO.Path]::GetFullPath((Join-Path $experiment 'build'))+[IO.Path]::DirectorySeparatorChar
    if(-not $build.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) {throw 'Build must stay inside this experiment/build'}
    if(Test-Path -LiteralPath $build) {throw 'Build directory must be fresh'}
    New-Item -ItemType Directory -Path $build | Out-Null
} else {
    if(-not $BuildDirectory) {throw 'Run requires -BuildDirectory from a successful build'}
    $build=(Resolve-Path -LiteralPath $BuildDirectory).Path
}
$manifestPath=Join-Path $build 'build_manifest.json'
$manifestReceipt=Join-Path $build 'build_manifest.sha256'
$exe=Join-Path $build 'matcher_contract.exe'
if($Mode -eq 'Build') {
    $flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra','-Wno-sign-compare',"-I$OpenCV/build")
    foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {$flags+="-I$OpenCV/modules/$module/include"}
    $base=Join-Path $experiment 'baseline';$candidate=Join-Path $experiment 'candidate'
    $units=@(
        @{source=(Join-Path $experiment 'v11_reference.cpp');object=(Join-Path $build 'v11_reference.o');includes=@("-I$base","-I$base/MIPP")},
        @{source=(Join-Path $candidate 'line2Dup.cpp');object=(Join-Path $build 'candidate.o');includes=@("-I$candidate","-I$base/MIPP")},
        @{source=(Join-Path $experiment 'tests\matcher_contract_test.cpp');object=(Join-Path $build 'matcher_contract.o');includes=@("-I$candidate","-I$base/MIPP")}
    )
    $results=@();$ok=$true;$started=Get-Date -Format o
    foreach($unit in $units) {
        $argv=@($flags)+@($unit.includes)+@('-c',$unit.source,'-o',$unit.object)
        $ErrorActionPreference='Continue'
        $out=@(& $Compiler @argv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
        $ErrorActionPreference='Stop'
        $results+=@{source=$unit.source;argv=$argv;exit_code=$code;output=$out}
        $out | Write-Output
        if($code -ne 0) {$ok=$false;break}
    }
    if($ok) {
        $argv=@('-fopenmp')+@($units.object)+@("-L$OpenCV/build/lib",'-lopencv_world4120','-o',$exe)
        $ErrorActionPreference='Continue'
        $out=@(& $Compiler @argv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
        $ErrorActionPreference='Stop'
        $results+=@{source='link';argv=$argv;exit_code=$code;output=$out};$out | Write-Output
        $ok=($code -eq 0)
    }
    $changes=@()
    foreach($path in $paths) {if((Get-FileHash -LiteralPath $path).Hash -ne $hashes[$path]) {$changes+=$path}}
    foreach($path in $protected) {if((Get-FileHash -LiteralPath $path).Hash -ne $protectedHashes[$path]) {$changes+=$path}}
    $built=[ordered]@{passed=($ok -and $changes.Count -eq 0);started_at=$started;finished_at=(Get-Date -Format o);
        baseline_commit=$baseline.commit;source_sha256=$hashes;protected_source_sha256=$protectedHashes;
        compiler=$Compiler;compiler_sha256=(Get-FileHash -LiteralPath $Compiler).Hash;compilation=$results;
        source_changes_during_build=$changes;executable=$exe;
        executable_sha256=$(if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe).Hash} else {$null});
        limitation='Compilation only; no matcher call, correctness pass, speed or accuracy claim.'}
    $built | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $built | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $experiment ('matcher_build_'+$stamp+'.json')) -Encoding UTF8
    (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash | Set-Content -LiteralPath $manifestReceipt -Encoding ASCII
    if(-not $built.passed) {throw 'Matcher build failed; all compiler evidence retained'}
    Write-Output "Build complete; no matcher executed: $build"
    exit 0
}
$manifestExpected=(Get-Content -LiteralPath $manifestReceipt -Raw).Trim()
if($manifestExpected -notmatch '^[0-9a-fA-F]{64}$') {throw 'Build manifest SHA256 receipt is invalid'}
$manifestHashBefore=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
$receiptHashBefore=(Get-FileHash -LiteralPath $manifestReceipt -Algorithm SHA256).Hash
if($manifestHashBefore -ne $manifestExpected) {throw 'Build manifest differs from its SHA256 receipt'}
$built=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if(-not $built.passed) {throw 'Build is not successful'}
foreach($item in $built.source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $item.Name).Hash -ne $item.Value) {throw "Source/input changed since build: $($item.Name)"}
}
foreach($item in $built.protected_source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $item.Name).Hash -ne $item.Value) {throw "Protected source changed since build: $($item.Name)"}
}
$executableHashBefore=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if($executableHashBefore -ne $built.executable_sha256) {throw 'Executable changed since build'}
$csv=Join-Path $experiment ('correctness_'+$Stage+'_'+$stamp+'.csv')
$json=Join-Path $experiment ('correctness_'+$Stage+'_'+$stamp+'.json')
if((Test-Path -LiteralPath $csv) -or (Test-Path -LiteralPath $json)) {throw 'Correctness evidence path must be fresh'}
$started=Get-Date -Format o
$ErrorActionPreference='Continue'
$out=@(& $exe --stage $Stage --output $csv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
$ErrorActionPreference='Stop'
$manifestHashAfter=if(Test-Path -LiteralPath $manifestPath) {(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash} else {$null}
$receiptHashAfter=if(Test-Path -LiteralPath $manifestReceipt) {(Get-FileHash -LiteralPath $manifestReceipt -Algorithm SHA256).Hash} else {$null}
$executableHashAfter=if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash} else {$null}
$manifestChanged=($manifestHashAfter -ne $manifestHashBefore)
$receiptChanged=($receiptHashAfter -ne $receiptHashBefore)
$executableChanged=($executableHashAfter -ne $executableHashBefore)
$changes=@()
foreach($path in $paths) {if((Get-FileHash -LiteralPath $path).Hash -ne $hashes[$path]) {$changes+=$path}}
foreach($path in $protected) {if((Get-FileHash -LiteralPath $path).Hash -ne $protectedHashes[$path]) {$changes+=$path}}
$rows=@();if(Test-Path -LiteralPath $csv) {$rows=@(Import-Csv -LiteralPath $csv)}
$matrix=Get-Content -LiteralPath (Join-Path $experiment 'REGRESSION_MATRIX.json') -Raw | ConvertFrom-Json
$expectedRows=if($Stage -eq 'all') {$matrix.all_expected_csv_rows} else {$matrix.$Stage.expected_csv_rows}
$bad=@($rows | Where-Object {$_.full_ordered_equal -ne '1'})
$passed=($code -eq 0 -and $changes.Count -eq 0 -and $rows.Count -eq $expectedRows -and $bad.Count -eq 0 -and
    -not $manifestChanged -and -not $receiptChanged -and -not $executableChanged)
$result=[ordered]@{passed=$passed;stage=$Stage;started_at=$started;finished_at=(Get-Date -Format o);exit_code=$code;
    source_sha256=$hashes;protected_source_sha256=$protectedHashes;source_changes_during_run=$changes;
    build_manifest_path=$manifestPath;build_manifest_expected_sha256=$manifestExpected;
    build_manifest_sha256_before=$manifestHashBefore;build_manifest_sha256_after=$manifestHashAfter;build_manifest_changed=$manifestChanged;
    build_manifest_receipt_sha256_before=$receiptHashBefore;build_manifest_receipt_sha256_after=$receiptHashAfter;build_manifest_receipt_changed=$receiptChanged;
    executable_path=$exe;executable_sha256_before=$executableHashBefore;executable_sha256_after=$executableHashAfter;executable_changed=$executableChanged;
    build_manifest=$built;csv=$csv;csv_sha256=$(if(Test-Path -LiteralPath $csv) {(Get-FileHash -LiteralPath $csv).Hash} else {$null});
    rows=$rows.Count;expected_rows=$expectedRows;mismatches=$bad.Count;output=$out;
    cv_threads=1;omp_wait_policy='PASSIVE';omp_dynamic='FALSE';omp_max_active_levels=1;
    correctness_contract='Complete ordered class/x/y/template identity/float32 bits/length against separately compiled exact V11; no set/canonicalization substitute.';
    limitation='Correctness regression only; no controlled speed benchmark or accuracy-improvement claim. No heldout RGB decode/view/match.'}
$result | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $json -Encoding UTF8
$out | Write-Output
Write-Output "Evidence: $json"
if(-not $passed) {throw 'Matcher correctness failed; CSV/console/source evidence retained'}
