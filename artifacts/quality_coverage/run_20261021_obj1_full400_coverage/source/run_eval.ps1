param(
    [ValidateSet('selftest','evaluate')][string]$Mode='selftest',
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Dataset='',
    [string]$Training='',
    [string]$RawRun='',
    [switch]$RunEvaluation,
    [string]$OpenCV='D:\opencv-4.12.0',
    [string]$CompilerBin='F:\mysys2\ucrt64\bin'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$OpenCV\build\bin;$CompilerBin;$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
if(Test-Path -LiteralPath $OutputDirectory){throw 'Output must be a new directory'}
if($Mode -eq 'evaluate' -and (-not $RunEvaluation -or -not $Dataset -or -not $Training -or -not $RawRun)){throw 'Evaluate requires Dataset/Training/RawRun and -RunEvaluation; coordinate CPU first'}
$build=Join-Path $PSScriptRoot 'build';$buildManifest=Join-Path $build 'build_manifest.json'
$manifest=Get-Content -LiteralPath $buildManifest -Raw|ConvertFrom-Json
foreach($property in $manifest.source_sha256.PSObject.Properties){
    if((Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash -ne $property.Value){throw "Source changed since verified build: $($property.Name)"}
}
$exe=Join-Path $build 'coverage_eval.exe'
if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $manifest.executable_sha256){throw 'Coverage executable changed'}
$started=Get-Date -Format o
$argv=@('--mode',$Mode,'--output',$OutputDirectory)
$verifiedPath=$OutputDirectory+'.verified_before.json'
$verifiedHash=''
if($Mode -eq 'evaluate'){
    if(Test-Path -LiteralPath $verifiedPath){throw 'Verified input evidence must be fresh'}
    & py -3.10 (Join-Path $PSScriptRoot 'verify_raw_provenance.py') '--dataset' $Dataset '--training' $Training '--raw-run' $RawRun '--output' $verifiedPath
    if($LASTEXITCODE -ne 0){throw 'Raw provenance audit failed; no coverage images evaluated'}
    $verified=Get-Content -LiteralPath $verifiedPath -Raw|ConvertFrom-Json
    if($verified.verified -ne 1 -or $verified.split -ne 'development'){throw 'Only verified development raw may run'}
    $verifiedHash=(Get-FileHash -LiteralPath $verifiedPath -Algorithm SHA256).Hash
    foreach($inputItem in $verified.input_sha256){if((Get-FileHash -LiteralPath $inputItem.path -Algorithm SHA256).Hash -ne $inputItem.sha256){throw "Verified input changed before evaluation: $($inputItem.path)"}}
    $argv+=@('--verified',$verifiedPath)
}
$startInfo=New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName=$exe
$startInfo.Arguments=($argv|ForEach-Object {'"'+($_ -replace '"','\"')+'"'}) -join ' '
$startInfo.UseShellExecute=$false;$startInfo.CreateNoWindow=$true;$startInfo.RedirectStandardOutput=$true;$startInfo.RedirectStandardError=$true
$process=New-Object System.Diagnostics.Process;$process.StartInfo=$startInfo
[void]$process.Start();$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync();$process.WaitForExit();$result=$process.ExitCode
[IO.File]::WriteAllText($OutputDirectory+'.stdout.txt',$stdout.Result)
[IO.File]::WriteAllText($OutputDirectory+'.stderr.txt',$stderr.Result)
Write-Output $stdout.Result
if($stderr.Result){Write-Output $stderr.Result}
if($Mode -eq 'evaluate'){
    if((Get-FileHash -LiteralPath $verifiedPath -Algorithm SHA256).Hash -ne $verifiedHash){throw 'Verified input evidence changed during run'}
    foreach($inputItem in $verified.input_sha256){if((Get-FileHash -LiteralPath $inputItem.path -Algorithm SHA256).Hash -ne $inputItem.sha256){throw "Verified input changed during evaluation: $($inputItem.path)"}}
}
foreach($property in $manifest.source_sha256.PSObject.Properties){
    if((Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash -ne $property.Value){throw "Source changed during selftest: $($property.Name)"}
}
if(Test-Path -LiteralPath $OutputDirectory){
    Copy-Item -LiteralPath $buildManifest -Destination (Join-Path $OutputDirectory 'build_manifest.json')
    $snapshot=Join-Path $OutputDirectory 'source';New-Item -ItemType Directory -Path $snapshot|Out-Null
    foreach($name in @('coverage_eval.cpp','coverage_helper.hpp','coverage_nms.hpp','COVERAGE_PROTOCOL.json','build_eval.ps1','run_eval.ps1','verify_raw_provenance.py')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $snapshot $name)}
    if($Mode -eq 'evaluate'){Copy-Item -LiteralPath $verifiedPath -Destination (Join-Path $OutputDirectory 'verified_inputs.json')}
    Copy-Item -LiteralPath ($OutputDirectory+'.stdout.txt') -Destination (Join-Path $OutputDirectory 'stdout.txt')
    Copy-Item -LiteralPath ($OutputDirectory+'.stderr.txt') -Destination (Join-Path $OutputDirectory 'stderr.txt')
    $outputHashes=[ordered]@{}
    foreach($file in (Get-ChildItem -LiteralPath $OutputDirectory -File)){$outputHashes[$file.Name]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
    @{started_at=$started;finished_at=(Get-Date -Format o);mode=$Mode;argv=$argv;exit_code=$result;dataset_images_evaluated=[int]($Mode -eq 'evaluate');heldout_images_read=0;
        executable_sha256=$manifest.executable_sha256;build_manifest_sha256=(Get-FileHash -LiteralPath $buildManifest -Algorithm SHA256).Hash;
        verified_inputs_sha256=$verifiedHash;sources_unchanged=$true;inputs_unchanged=$true;output_sha256=$outputHashes;
        scope='Frozen actual85 development coverage comparison; no heldout mode, no paired performance claim'}|
        ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $OutputDirectory 'execution_provenance.json') -Encoding UTF8
}
if($result -ne 0){throw "Coverage selftest failed ($result); preserve output"}
