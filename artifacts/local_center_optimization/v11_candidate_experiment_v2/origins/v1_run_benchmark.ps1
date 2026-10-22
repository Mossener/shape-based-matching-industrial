param(
    [Parameter(Mandatory=$true)][ValidateSet('Build','Run')][string]$Mode,
    [Parameter(Mandatory=$true)][string[]]$CorrectnessEvidence,
    [Parameter(Mandatory=$true)][string]$ValidatorEvidence,
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
if($CorrectnessEvidence.Count -ne 3) {throw 'Exactly three successful correctness stages required'}
$gates=@();$stageNames=@();$sourceHashes=[ordered]@{};$protectedHashes=[ordered]@{};$gateExecutable=$null
foreach($path in $CorrectnessEvidence) {
    $resolved=(Resolve-Path -LiteralPath $path).Path
    if(-not $resolved.StartsWith($experiment+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {throw 'Correctness evidence must belong to this experiment'}
    $gate=Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
    if(-not $gate.passed -or $gate.exit_code -ne 0 -or $gate.mismatches -ne 0 -or $gate.rows -ne $gate.expected_rows -or
       $gate.build_manifest_changed -or $gate.build_manifest_receipt_changed -or $gate.executable_changed -or
       @($gate.source_changes_during_run).Count -ne 0) {throw "Invalid correctness gate: $resolved"}
    if($gate.stage -notin @('core','flags','lifetime')) {throw 'Unknown correctness gate stage'}
    if(-not $gate.build_manifest_expected_sha256 -or $gate.build_manifest_sha256_before -ne $gate.build_manifest_expected_sha256 -or
       $gate.build_manifest_sha256_after -ne $gate.build_manifest_expected_sha256 -or
       $gate.executable_sha256_before -ne $gate.build_manifest.executable_sha256 -or
       $gate.executable_sha256_after -ne $gate.build_manifest.executable_sha256) {throw 'Correctness build/executable hashes were not preserved'}
    if($gateExecutable -and $gateExecutable -ne $gate.executable_sha256_before) {throw 'Correctness stages must use the identical executable'}
    $gateExecutable=$gate.executable_sha256_before
    if((Get-FileHash -LiteralPath $gate.csv -Algorithm SHA256).Hash -ne $gate.csv_sha256) {throw 'Correctness CSV changed'}
    foreach($item in $gate.source_sha256.PSObject.Properties) {
        if($sourceHashes.Contains($item.Name) -and $sourceHashes[$item.Name] -ne $item.Value) {throw 'Correctness stage source identities differ'}
        if((Get-FileHash -LiteralPath $item.Name -Algorithm SHA256).Hash -ne $item.Value) {throw "Correctness source changed: $($item.Name)"}
        $sourceHashes[$item.Name]=$item.Value
    }
    foreach($item in $gate.protected_source_sha256.PSObject.Properties) {
        if($protectedHashes.Contains($item.Name) -and $protectedHashes[$item.Name] -ne $item.Value) {throw 'Protected source identities differ'}
        if((Get-FileHash -LiteralPath $item.Name -Algorithm SHA256).Hash -ne $item.Value) {throw "Protected source changed: $($item.Name)"}
        $protectedHashes[$item.Name]=$item.Value
    }
    foreach($item in @($resolved,$gate.csv)) {$sourceHashes[$item]=(Get-FileHash -LiteralPath $item -Algorithm SHA256).Hash}
    $stageNames+=$gate.stage
    $gates+=@{path=$resolved;sha256=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash;stage=$gate.stage;csv_sha256=$gate.csv_sha256}
}
if((@($stageNames | Sort-Object -Unique) -join ',') -ne 'core,flags,lifetime') {throw 'All three distinct stages required'}
$validatorPath=(Resolve-Path -LiteralPath $ValidatorEvidence).Path
$validator=Get-Content -LiteralPath $validatorPath -Raw | ConvertFrom-Json
$validatorTest=Join-Path $experiment 'tests\summary_contract_test.py'
if(-not $validator.passed -or -not $validator.synthetic_only -or $validator.matcher_calls -ne 0 -or $validator.image_decodes -ne 0 -or
   @($validator.outcomes).Count -ne 14 -or -not $validator.outcomes[0].accepted -or
   @($validator.outcomes | Select-Object -Skip 1 | Where-Object {-not $_.rejected}).Count -ne 0 -or
   (Get-FileHash -LiteralPath (Join-Path $experiment 'summarize.py')).Hash -ne $validator.summary_source_sha256 -or
   (Get-FileHash -LiteralPath $validatorTest).Hash -ne $validator.test_source_sha256) {throw 'Current summary validator fourteen-case GREEN evidence required'}
$validatorGate=@{path=$validatorPath;sha256=(Get-FileHash -LiteralPath $validatorPath).Hash}
$contractText=[IO.File]::ReadAllText((Join-Path $experiment 'tests\matcher_contract_test.cpp'))
$fixtureBoundary=$contractText.IndexOf('class Audit {',[StringComparison]::Ordinal)
if($fixtureBoundary -lt 0) {throw 'Correctness fixture extraction boundary missing'}
$expectedFixture=$contractText.Substring(0,$fixtureBoundary).Replace('"../../../led_match/led_demo.cpp"','"../../led_match/led_demo.cpp"').Replace('"../v11_reference.hpp"','"v11_reference.hpp"')+"}`n"
$fixtureHeader=Join-Path $experiment 'benchmark_fixtures.hpp'
if([IO.File]::ReadAllText($fixtureHeader) -cne $expectedFixture) {throw 'Benchmark fixtures diverge from correctness-tested prefix (only relative include relocation allowed)'}
foreach($path in @($PSCommandPath,(Join-Path $experiment 'benchmark.cpp'),$fixtureHeader,(Join-Path $experiment 'BENCHMARK_PROTOCOL.json'),(Join-Path $experiment 'summarize.py'),$validatorTest,$validatorPath)) {
    $sourceHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
$runtimePaths=@("$OpenCV/build/bin/libopencv_world4120.dll",
    (Join-Path (Split-Path -Parent $Compiler) 'libgomp-1.dll'),
    (Join-Path (Split-Path -Parent $Compiler) 'libstdc++-6.dll'),
    (Join-Path (Split-Path -Parent $Compiler) 'libgcc_s_seh-1.dll'))
foreach($path in (@($Compiler)+$runtimePaths)) {$sourceHashes[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
if($Mode -eq 'Build') {
    if(-not $BuildDirectory) {$BuildDirectory=Join-Path $experiment ('build\benchmark_'+$stamp)}
    $build=[IO.Path]::GetFullPath($BuildDirectory)
    $allowed=[IO.Path]::GetFullPath((Join-Path $experiment 'build'))+[IO.Path]::DirectorySeparatorChar
    if(-not $build.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) {throw 'Build must stay inside experiment/build'}
    if(Test-Path -LiteralPath $build) {throw 'Build directory must be fresh'}
    New-Item -ItemType Directory -Path $build | Out-Null
} else {
    if(-not $BuildDirectory) {throw 'Run requires a successful -BuildDirectory'}
    $build=(Resolve-Path -LiteralPath $BuildDirectory).Path
}
$manifestPath=Join-Path $build 'build_manifest.json'
$receipt=Join-Path $build 'build_manifest.sha256'
$exe=Join-Path $build 'benchmark.exe'
if($Mode -eq 'Build') {
    $flags=@('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra','-Wno-sign-compare',"-I$OpenCV/build")
    foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')) {$flags+="-I$OpenCV/modules/$module/include"}
    $base=Join-Path $experiment 'baseline';$candidate=Join-Path $experiment 'candidate'
    $units=@(
        @{source=(Join-Path $experiment 'v11_reference.cpp');object=(Join-Path $build 'v11_reference.o');includes=@("-I$base","-I$base/MIPP")},
        @{source=(Join-Path $candidate 'line2Dup.cpp');object=(Join-Path $build 'candidate.o');includes=@("-I$candidate","-I$base/MIPP")},
        @{source=(Join-Path $experiment 'benchmark.cpp');object=(Join-Path $build 'benchmark.o');includes=@("-I$candidate","-I$base/MIPP")}
    )
    $results=@();$ok=$true;$started=Get-Date -Format o
    foreach($unit in $units) {
        $argv=@($flags)+@($unit.includes)+@('-c',$unit.source,'-o',$unit.object)
        $ErrorActionPreference='Continue'
        $out=@(& $Compiler @argv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
        $ErrorActionPreference='Stop'
        $results+=@{source=$unit.source;argv=$argv;exit_code=$code;output=$out};$out | Write-Output
        if($code -ne 0) {$ok=$false;break}
    }
    if($ok) {
        $argv=@('-fopenmp')+@($units.object)+@("-L$OpenCV/build/lib",'-lopencv_world4120','-o',$exe)
        $ErrorActionPreference='Continue'
        $out=@(& $Compiler @argv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
        $ErrorActionPreference='Stop'
        $results+=@{source='link';argv=$argv;exit_code=$code;output=$out};$out | Write-Output;$ok=($code -eq 0)
    }
    $changes=@()
    foreach($item in $sourceHashes.GetEnumerator()) {if((Get-FileHash -LiteralPath $item.Key).Hash -ne $item.Value) {$changes+=$item.Key}}
    foreach($item in $protectedHashes.GetEnumerator()) {if((Get-FileHash -LiteralPath $item.Key).Hash -ne $item.Value) {$changes+=$item.Key}}
    $built=[ordered]@{passed=($ok -and $changes.Count -eq 0);started_at=$started;finished_at=(Get-Date -Format o);
        correctness_gates=$gates;validator_gate=$validatorGate;source_sha256=$sourceHashes;protected_source_sha256=$protectedHashes;
        compiler=$Compiler;compiler_sha256=(Get-FileHash -LiteralPath $Compiler).Hash;compilation=$results;
        runtime_paths=$runtimePaths;os_version=[Environment]::OSVersion.VersionString;
        processor_identifier=$env:PROCESSOR_IDENTIFIER;processor_architecture=$env:PROCESSOR_ARCHITECTURE;
        logical_processor_count=[Environment]::ProcessorCount;
        source_changes_during_build=$changes;executable=$exe;
        executable_sha256=$(if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe).Hash} else {$null});
        limitation='Benchmark compilation only; no speed or accuracy claim.'}
    $built | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $built | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $experiment ('benchmark_build_'+$stamp+'.json')) -Encoding UTF8
    (Get-FileHash -LiteralPath $manifestPath).Hash | Set-Content -LiteralPath $receipt -Encoding ASCII
    if(-not $built.passed) {throw 'Benchmark build failed; compiler evidence retained'}
    Write-Output "Benchmark build complete; no matcher executed: $build";exit 0
}
$manifestExpected=(Get-Content -LiteralPath $receipt -Raw).Trim()
$manifestBefore=(Get-FileHash -LiteralPath $manifestPath).Hash;$receiptBefore=(Get-FileHash -LiteralPath $receipt).Hash
if($manifestExpected -notmatch '^[0-9a-fA-F]{64}$' -or $manifestBefore -ne $manifestExpected) {throw 'Benchmark build manifest SHA256 receipt failed'}
$built=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if(-not $built.passed) {throw 'Benchmark build is not successful'}
if($built.validator_gate.path -ne $validatorGate.path -or $built.validator_gate.sha256 -ne $validatorGate.sha256) {throw 'Run validator gate differs from original benchmark build'}
if(-not [String]::Equals([IO.Path]::GetFullPath($Compiler),[IO.Path]::GetFullPath($built.compiler),[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Run compiler directory differs from original benchmark build'
}
if($runtimePaths.Count -ne @($built.runtime_paths).Count) {throw 'Run runtime path count differs from original build'}
for($i=0;$i -lt $runtimePaths.Count;++$i) {
    if(-not [String]::Equals([IO.Path]::GetFullPath($runtimePaths[$i]),[IO.Path]::GetFullPath($built.runtime_paths[$i]),[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Run runtime DLL search directories differ from original benchmark build'
    }
}
foreach($original in $built.correctness_gates) {
    $current=@($gates | Where-Object {$_.stage -eq $original.stage})
    if($current.Count -ne 1 -or $current[0].path -ne $original.path -or $current[0].sha256 -ne $original.sha256 -or
       $current[0].csv_sha256 -ne $original.csv_sha256) {throw 'Run correctness gates differ from original benchmark build'}
}
foreach($group in @($built.source_sha256,$built.protected_source_sha256)) {
    foreach($item in $group.PSObject.Properties) {if((Get-FileHash -LiteralPath $item.Name).Hash -ne $item.Value) {throw "Source changed since benchmark build: $($item.Name)"}}
}
$exeBefore=(Get-FileHash -LiteralPath $exe).Hash
if($exeBefore -ne $built.executable_sha256) {throw 'Benchmark executable changed'}
$csv=Join-Path $experiment ('benchmark_'+$stamp+'.csv');$json=Join-Path $experiment ('benchmark_'+$stamp+'.json')
if((Test-Path -LiteralPath $csv) -or (Test-Path -LiteralPath $json)) {throw 'Benchmark evidence paths must be fresh'}
$started=Get-Date -Format o
$ErrorActionPreference='Continue'
$out=@(& $exe --output $csv 2>&1 | ForEach-Object {"$_"});$code=$LASTEXITCODE
$ErrorActionPreference='Stop'
$manifestAfter=if(Test-Path -LiteralPath $manifestPath) {(Get-FileHash -LiteralPath $manifestPath).Hash} else {$null}
$receiptAfter=if(Test-Path -LiteralPath $receipt) {(Get-FileHash -LiteralPath $receipt).Hash} else {$null}
$exeAfter=if(Test-Path -LiteralPath $exe) {(Get-FileHash -LiteralPath $exe).Hash} else {$null}
$changes=@()
foreach($group in @($built.source_sha256,$built.protected_source_sha256)) {
    foreach($item in $group.PSObject.Properties) {if((Get-FileHash -LiteralPath $item.Name).Hash -ne $item.Value) {$changes+=$item.Name}}
}
$rows=@();if(Test-Path -LiteralPath $csv) {$rows=@(Import-Csv -LiteralPath $csv)}
$bad=@($rows | Where-Object {$_.full_ordered_equal -ne '1'})
$passed=($code -eq 0 -and $changes.Count -eq 0 -and $rows.Count -eq 1350 -and $bad.Count -eq 0 -and
    $manifestAfter -eq $manifestBefore -and $receiptAfter -eq $receiptBefore -and $exeAfter -eq $exeBefore)
$result=[ordered]@{passed=$passed;started_at=$started;finished_at=(Get-Date -Format o);exit_code=$code;
    correctness_gates=$built.correctness_gates;validator_gate=$built.validator_gate;source_sha256=$built.source_sha256;protected_source_sha256=$built.protected_source_sha256;source_changes_during_run=$changes;
    runtime_paths=$built.runtime_paths;os_version=[Environment]::OSVersion.VersionString;
    processor_identifier=$env:PROCESSOR_IDENTIFIER;processor_architecture=$env:PROCESSOR_ARCHITECTURE;
    logical_processor_count=[Environment]::ProcessorCount;
    build_manifest_path=$manifestPath;build_manifest_expected_sha256=$manifestExpected;build_manifest_sha256_before=$manifestBefore;
    build_manifest_sha256_after=$manifestAfter;build_manifest_changed=($manifestAfter -ne $manifestBefore);
    build_manifest_receipt_sha256_before=$receiptBefore;build_manifest_receipt_sha256_after=$receiptAfter;build_manifest_receipt_changed=($receiptAfter -ne $receiptBefore);
    executable=$exe;executable_sha256_before=$exeBefore;executable_sha256_after=$exeAfter;executable_changed=($exeAfter -ne $exeBefore);
    csv=$csv;csv_sha256=$(if(Test-Path -LiteralPath $csv) {(Get-FileHash -LiteralPath $csv).Hash} else {$null});
    rows=$rows.Count;expected_rows=1350;mismatches=$bad.Count;output=$out;
    protocol_sha256=(Get-FileHash -LiteralPath (Join-Path $experiment 'BENCHMARK_PROTOCOL.json')).Hash;
    limitation='Controlled exact-output speed experiment only; no accuracy improvement or production adoption.'}
$result | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $json -Encoding UTF8
$out | Write-Output;Write-Output "Evidence: $json"
if(-not $passed) {throw 'Benchmark failed; all evidence retained'}
