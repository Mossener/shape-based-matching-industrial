param(
    [ValidateSet('selftest','pilot','development','timing')][string]$Mode='selftest',
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$PilotDirectory='',
    [string]$QualityDirectory='',
    [switch]$RunMatches,
    [switch]$CpuSlotGranted,
    [string]$OpenCV='D:\opencv-4.12.0',
    [string]$CompilerBin='F:\mysys2\ucrt64\bin'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH="$OpenCV\build\bin;$CompilerBin;$env:PATH"
$env:OMP_NUM_THREADS='4';$env:OMP_DYNAMIC='FALSE';$env:OMP_MAX_ACTIVE_LEVELS='1';$env:OMP_WAIT_POLICY='PASSIVE'
if(Test-Path -LiteralPath $OutputDirectory){throw 'Output directory must be new'}
if($Mode -ne 'selftest' -and (-not $RunMatches -or -not $CpuSlotGranted)){throw 'Matching requires declared CPU slot and -RunMatches'}
$build=Join-Path $PSScriptRoot 'build';$manifestPath=Join-Path $build 'build_manifest.json'
$manifestHash=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
foreach($property in $manifest.source_sha256.PSObject.Properties){if((Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash -ne $property.Value){throw "Source changed since build: $($property.Name)"}}
$exe=Join-Path $build 'padding_eval.exe'
if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $manifest.executable_sha256){throw 'Padding executable changed'}
function Check-CompletedRun([string]$Directory,[string]$Stage,[int]$Frames){
    if(-not $Directory){throw "Missing completed $Stage run"}
    $p=Get-Content -LiteralPath (Join-Path $Directory 'execution_provenance.json') -Raw|ConvertFrom-Json
    $m=Get-Content -LiteralPath (Join-Path $Directory 'comparison_metrics.json') -Raw|ConvertFrom-Json
    if($p.exit_code -ne 0 -or $p.executable_sha256 -ne $manifest.executable_sha256 -or $p.build_manifest_sha256 -ne $manifestHash -or $m.stage -ne $Stage -or $m.frames -ne $Frames -or $m.all_fallback_fused_fields_exact -ne 1){throw "Incomplete/changed $Stage reference"}
    foreach($property in $p.output_sha256.PSObject.Properties){if((Get-FileHash -LiteralPath (Join-Path $Directory $property.Name) -Algorithm SHA256).Hash -ne $property.Value){throw "Changed $Stage reference output: $($property.Name)"}}
}
if($Mode -eq 'development'){Check-CompletedRun $PilotDirectory 'pilot' 8}
if($Mode -eq 'timing'){Check-CompletedRun $QualityDirectory 'development' 400}
$argv=@('--mode',$Mode,'--output',$OutputDirectory);$verifiedPath=$OutputDirectory+'.verified_before.json';$verifiedHash=''
if($Mode -ne 'selftest'){
    if(Test-Path -LiteralPath $verifiedPath){throw 'Verified evidence must be new'}
    & py -3.10 (Join-Path $PSScriptRoot 'verify_inputs.py') --mode $Mode --output $verifiedPath
    if($LASTEXITCODE -ne 0){throw 'Padding source/raw/input provenance failed; no image decoded'}
    $verified=Get-Content -LiteralPath $verifiedPath -Raw|ConvertFrom-Json
    $verifiedHash=(Get-FileHash -LiteralPath $verifiedPath -Algorithm SHA256).Hash
    foreach($item in $verified.input_sha256){if((Get-FileHash -LiteralPath $item.path -Algorithm SHA256).Hash -ne $item.sha256){throw "Input changed before run: $($item.path)"}}
    $argv+=@('--verified',$verifiedPath)
}
if($Mode -eq 'timing'){$argv+=@('--quality',$QualityDirectory)}
$began=Get-Date -Format o
$info=New-Object System.Diagnostics.ProcessStartInfo;$info.FileName=$exe
$info.Arguments=($argv|ForEach-Object {'"'+($_ -replace '"','\"')+'"'}) -join ' '
$info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
$process=New-Object System.Diagnostics.Process;$process.StartInfo=$info
[void]$process.Start();$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync();$process.WaitForExit();$code=$process.ExitCode
[IO.File]::WriteAllText($OutputDirectory+'.stdout.txt',$stdout.Result);[IO.File]::WriteAllText($OutputDirectory+'.stderr.txt',$stderr.Result)
Write-Output $stdout.Result;if($stderr.Result){Write-Output $stderr.Result}
if($Mode -ne 'selftest'){
    if((Get-FileHash -LiteralPath $verifiedPath -Algorithm SHA256).Hash -ne $verifiedHash){throw 'Verified evidence changed during run'}
    foreach($item in $verified.input_sha256){if((Get-FileHash -LiteralPath $item.path -Algorithm SHA256).Hash -ne $item.sha256){throw "Input changed during run: $($item.path)"}}
}
foreach($property in $manifest.source_sha256.PSObject.Properties){if((Get-FileHash -LiteralPath $property.Name -Algorithm SHA256).Hash -ne $property.Value){throw "Source changed during run: $($property.Name)"}}
if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $manifest.executable_sha256){throw 'Padding executable changed during run'}
if((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ne $manifestHash){throw 'Padding build manifest changed during run'}
if($Mode -eq 'timing'){Check-CompletedRun $QualityDirectory 'development' 400}
if(Test-Path -LiteralPath $OutputDirectory){
    Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $OutputDirectory 'build_manifest.json')
    Copy-Item -LiteralPath ($OutputDirectory+'.stdout.txt') -Destination (Join-Path $OutputDirectory 'stdout.txt');Copy-Item -LiteralPath ($OutputDirectory+'.stderr.txt') -Destination (Join-Path $OutputDirectory 'stderr.txt')
    if($Mode -ne 'selftest'){Copy-Item -LiteralPath $verifiedPath -Destination (Join-Path $OutputDirectory 'verified_inputs.json')}
    $snapshot=Join-Path $OutputDirectory 'source';New-Item -ItemType Directory -Path $snapshot|Out-Null
    $copied=[ordered]@{}
    foreach($property in $manifest.source_sha256.PSObject.Properties){
        $name=[IO.Path]::GetFileName($property.Name)
        if($name -eq 'build_manifest.json'){$name='frozen_public_build_manifest.json'}
        $dest=Join-Path $snapshot $name
        if(Test-Path -LiteralPath $dest){if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -ne $property.Value){throw 'Snapshot filename collision'}}else{Copy-Item -LiteralPath $property.Name -Destination $dest}
        $copied[$property.Name]='source/'+$name
    }
    $copied|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $OutputDirectory 'source_snapshot_paths.json') -Encoding UTF8
    $hashes=[ordered]@{};$rootPath=[IO.Path]::GetFullPath($OutputDirectory)
    foreach($file in (Get-ChildItem -LiteralPath $OutputDirectory -File -Recurse)){$relative=$file.FullName.Substring($rootPath.Length+1).Replace('\','/');$hashes[$relative]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
    @{started_at=$began;finished_at=(Get-Date -Format o);mode=$Mode;exit_code=$code;argv=$argv;executable_sha256=$manifest.executable_sha256;build_manifest_sha256=$manifestHash;verified_inputs_sha256=$verifiedHash;output_sha256=$hashes;sources_unchanged=$true;inputs_unchanged=$true;executable_unchanged=$true;build_manifest_unchanged=$true;heldout_images_read=0;opencv_threads=1;openmp_threads=4;scope='Frozen obj8 padding comparison; failures retained; no industrial accuracy claim'}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $OutputDirectory 'execution_provenance.json') -Encoding UTF8
}
if($code -ne 0){throw "Padding stage failed ($code); preserve failure and partial outputs"}
