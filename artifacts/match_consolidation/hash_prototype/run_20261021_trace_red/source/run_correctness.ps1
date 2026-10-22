param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet(0,1)][int]$ExpectedExit=0,
    [ValidateSet('hash_consolidation_test.cpp','trace_io_test.cpp')][string]$TestSource='hash_consolidation_test.cpp',
    [string]$MutationFile='',
    [string]$MutationOld='',
    [string]$MutationNew='',
    [int]$ExpectedMutationOccurrences=1,
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe'
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
Set-Location -LiteralPath $root
if(Test-Path -LiteralPath $OutputDirectory){throw 'Output must be a new directory'}
$core=Join-Path $root 'line2Dup_matches.hpp'
$expectedBlob=(& git rev-parse 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed:line2Dup_matches.hpp').Trim()
$actualBlob=(& git hash-object $core).Trim()
if($LASTEXITCODE -ne 0 -or $expectedBlob -ne $actualBlob){throw 'Production V11 consolidation header changed'}
$started=Get-Date -Format o
$out=New-Item -ItemType Directory -Path $OutputDirectory
$snapshot=New-Item -ItemType Directory -Path (Join-Path $out.FullName 'source')
$sources=[ordered]@{}
foreach($name in @('record.hpp','hash_consolidation.hpp','hash_consolidation_test.cpp','trace_io.hpp','trace_io_test.cpp','run_correctness.ps1')){
    $file=Join-Path $PSScriptRoot $name
    $sources[$file]=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    Copy-Item -LiteralPath $file -Destination (Join-Path $snapshot.FullName $name)
}
Copy-Item -LiteralPath $core -Destination (Join-Path $snapshot.FullName 'line2Dup_matches.hpp')
$sources[$core]=(Get-FileHash -LiteralPath $core -Algorithm SHA256).Hash
if($MutationFile){
    if($MutationFile -notin @('hash_consolidation.hpp','trace_io.hpp') -or -not $MutationOld -or $ExpectedMutationOccurrences -lt 1){throw 'Only explicit new prototype header mutations are supported'}
    $mutant=Join-Path $snapshot.FullName $MutationFile;$content=[IO.File]::ReadAllText($mutant)
    if(($content.Split([string[]]@($MutationOld),[StringSplitOptions]::None).Count-1) -ne $ExpectedMutationOccurrences){throw 'Mutation must match the declared exact occurrence count'}
    [IO.File]::WriteAllText($mutant,$content.Replace($MutationOld,$MutationNew),(New-Object Text.UTF8Encoding($false)))
}
$snapshotHashes=[ordered]@{}
foreach($file in (Get-ChildItem -LiteralPath $snapshot.FullName -File)){$snapshotHashes[$file.Name]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
$env:PATH="$(Split-Path -Parent $Compiler);$env:PATH"
function Invoke-Native([string]$File,[string[]]$Arguments,[string]$Prefix){
    $start=New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName=$File;$start.Arguments=($Arguments|ForEach-Object {'"'+($_ -replace '"','\"')+'"'}) -join ' '
    $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $process=New-Object System.Diagnostics.Process;$process.StartInfo=$start
    [void]$process.Start();$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync();$process.WaitForExit()
    [IO.File]::WriteAllText($Prefix+'_stdout.txt',$stdout.Result);[IO.File]::WriteAllText($Prefix+'_stderr.txt',$stderr.Result)
    return @{exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result}
}
$version=Invoke-Native $Compiler @('--version') (Join-Path $out.FullName 'compiler_version')
if($version.exit_code -ne 0){throw 'Compiler version query failed'}
$flags=@('-std=c++14','-O2','-Wall','-Wextra','-Werror',"-I$($snapshot.FullName)")
$exe=Join-Path $out.FullName ([IO.Path]::GetFileNameWithoutExtension($TestSource)+'.exe')
$compile=Invoke-Native $Compiler ($flags+@((Join-Path $snapshot.FullName $TestSource),'-o',$exe)) (Join-Path $out.FullName 'compile')
$compileExit=$compile.exit_code
$testExit=$null
if($compileExit -eq 0){
    $test=Invoke-Native $exe @() (Join-Path $out.FullName 'test')
    $testExit=$test.exit_code
}
foreach($file in $sources.Keys){if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $sources[$file]){throw "Source changed during run: $file"}}
foreach($name in $snapshotHashes.Keys){if((Get-FileHash -LiteralPath (Join-Path $snapshot.FullName $name) -Algorithm SHA256).Hash -ne $snapshotHashes[$name]){throw "Snapshot changed during run: $name"}}
$outputs=[ordered]@{}
foreach($file in (Get-ChildItem -LiteralPath $out.FullName -File)){$outputs[$file.Name]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
$ok=$compileExit -eq 0 -and $testExit -eq $ExpectedExit
@{status=$(if($ok){'PASS'}else{'FAIL'});started_at=$started;finished_at=(Get-Date -Format o);core_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed';core_blob=$actualBlob;
    compiler=$Compiler;compiler_sha256=(Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash;flags=$flags;source_sha256=$sources;snapshot_sha256=$snapshotHashes;output_sha256=$outputs;
    test_source=$TestSource;mutation_file=$MutationFile;mutation_old=$MutationOld;mutation_new=$MutationNew;expected_mutation_occurrences=$ExpectedMutationOccurrences;
    compile_exit=$compileExit;test_exit=$testExit;expected_test_exit=$ExpectedExit;sources_unchanged=$true;dataset_access=$false;matcher_calls=0;performance_benchmark=$false;
    scope='Isolated prototype correctness only; no production mutation or speed claim'}|
    ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $out.FullName 'validation.json') -Encoding UTF8
if(Test-Path -LiteralPath (Join-Path $out.FullName 'test_stdout.txt')){Get-Content -LiteralPath (Join-Path $out.FullName 'test_stdout.txt')}
if(Test-Path -LiteralPath (Join-Path $out.FullName 'test_stderr.txt')){Get-Content -LiteralPath (Join-Path $out.FullName 'test_stderr.txt')}
if($compile.stderr){Write-Output $compile.stderr}
if(-not $ok){throw "Unexpected prototype correctness result: compile=$compileExit test=$testExit expected=$ExpectedExit"}
