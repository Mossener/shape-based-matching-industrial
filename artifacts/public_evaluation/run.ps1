param(
    [Parameter(Mandatory=$true)][ValidateSet('inspect','train','pilot','develop','final','gzip-selftest')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Dataset = 'datasets/tless_expanded',
    [string]$Objects = '',
    [ValidateSet(32,48)][int]$Features = 32,
    [string]$TrainedDirectory = '',
    [string]$FrozenConfig = '',
    [switch]$RunMatches,
    [string]$OpenCV = 'D:\opencv-4.12.0',
    [string]$CompilerBin = 'F:\mysys2\ucrt64\bin'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
$env:PATH = "$OpenCV\build\bin;$CompilerBin;$env:PATH"
$env:OMP_NUM_THREADS='4'; $env:OMP_DYNAMIC='FALSE'; $env:OMP_MAX_ACTIVE_LEVELS='1'; $env:OMP_WAIT_POLICY='PASSIVE'
if(($Mode -eq 'pilot' -or $Mode -eq 'develop' -or $Mode -eq 'final') -and -not $RunMatches) { throw 'Matching requires -RunMatches; coordinate CPU first' }
$build = Join-Path $PSScriptRoot 'build'
$buildManifest = Get-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Raw | ConvertFrom-Json
foreach($source in $buildManifest.source_sha256.PSObject.Properties) {
    if((Get-FileHash -LiteralPath $source.Name -Algorithm SHA256).Hash -ne $source.Value) { throw "Source changed since build: $($source.Name)" }
}
$executable = Join-Path $build 'tless_eval.exe'
if((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $buildManifest.executable_sha256) { throw 'Executable hash changed since build' }
$schema = Get-Content -LiteralPath (Join-Path $Dataset 'index.json') -Raw | ConvertFrom-Json
if($Mode -ne 'gzip-selftest') {
    if($schema.schema_version -eq 2) {
        & python tools/datasets/verify_tless_expanded.py --output $Dataset --audit (Join-Path $build 'last_dataset_audit.json')
    } else {
        & python tools/datasets/fetch_tless_tiny.py --output $Dataset --verify-only
    }
    if($LASTEXITCODE -ne 0) { throw 'Dataset verification failed' }
}
$datasetManifest = if($schema.schema_version -eq 2) {'artifacts/public_datasets/tless_expanded_manifest.json'} else {'artifacts/public_datasets/tless_tiny_manifest.json'}
$inputs = @((Join-Path $Dataset 'index.json'),$datasetManifest,(Join-Path $build 'build_manifest.json'))
$argv = @('--mode',$Mode,'--dataset',$Dataset,'--output',$OutputDirectory)
if($Mode -eq 'train') { $argv += @('--features',"$Features") }
if($Objects) { $argv += @('--objects',$Objects) }
if($Mode -eq 'develop' -or $Mode -eq 'pilot') {
    if(-not $TrainedDirectory) { throw 'Develop needs -TrainedDirectory' }
    $argv += @('--trained',$TrainedDirectory)
}
if($Mode -eq 'final') {
    if(-not $FrozenConfig) { throw 'Final needs -FrozenConfig' }
    $argv += @('--frozen',$FrozenConfig)
    $inputs += $FrozenConfig
    $frozen = Get-Content -LiteralPath $FrozenConfig -Raw | ConvertFrom-Json
    $TrainedDirectory = $frozen.training_directory
}
if($TrainedDirectory) {
    $inputs += @((Join-Path $TrainedDirectory 'training_config.json'),(Join-Path $TrainedDirectory 'template_metadata.json'))
    $training = Get-Content -LiteralPath (Join-Path $TrainedDirectory 'training_config.json') -Raw | ConvertFrom-Json
    $targetObjects = if($training.target_objects) {@($training.target_objects)} else {@(1)}
    foreach($object in $targetObjects) { $inputs += (Join-Path $TrainedDirectory "templates_tless_object_$object.yml.gz") }
}
$before = [ordered]@{}
foreach($inputFile in $inputs) { $before[$inputFile] = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash }
$started = Get-Date -Format o
& $executable @argv
$result = $LASTEXITCODE
foreach($inputFile in $inputs) { if($before[$inputFile] -ne (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash) { throw "Input changed during run: $inputFile" } }
if(Test-Path -LiteralPath $OutputDirectory) {
    $rawArchives = @()
    foreach($archive in (Get-ChildItem -LiteralPath $OutputDirectory -Filter '*_raw.csv.gz' -File)) {
        $rawArchives += @{path=$archive.FullName;bytes=$archive.Length;sha256=(Get-FileHash -LiteralPath $archive.FullName -Algorithm SHA256).Hash}
    }
    @{started_at=$started;finished_at=(Get-Date -Format o);mode=$Mode;exit_code=$result;
      argv=$argv;build_manifest=(Get-Content -LiteralPath (Join-Path $build 'build_manifest.json') -Raw | ConvertFrom-Json);
      input_sha256=$before;raw_archives=$rawArchives;opencv_threads=1;openmp_threads=4} |
        ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'execution_provenance.json') -Encoding UTF8
}
if($result -ne 0) { throw "Adapter exited $result; retain output, do not hide failed equivalence or data errors" }
