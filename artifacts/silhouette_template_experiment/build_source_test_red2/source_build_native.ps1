param(
    [ValidateSet('source-test','adapter')][string]$Target='source-test',
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Set-Location -LiteralPath $root
$out=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $out){throw 'Build directory must be new'}
New-Item -ItemType Directory -Path $out|Out-Null
$env:PATH="$(Split-Path -Parent $Compiler);$OpenCV\build\bin;$env:PATH"
& py -3.10 (Join-Path $PSScriptRoot 'freeze_private_sources.py') --verify --output (Join-Path $out 'source_verify.json')
if($LASTEXITCODE -ne 0){throw 'Private V11 source audit failed; no compilation'}
$frozen=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'PRIVATE_SOURCE_FREEZE.json') -Raw|ConvertFrom-Json
$private=Join-Path $PSScriptRoot 'private_v11'
$core=Join-Path $private 'line2Dup.cpp'
if($frozen.core_translation_unit -cne $core){throw 'Build must compile experiment-private V11 core'}
$sourceName=if($Target -eq 'source-test'){'silhouette_source_test.cpp'}else{'silhouette_eval.cpp'}
$source=Join-Path $PSScriptRoot $sourceName
$sources=[ordered]@{}
foreach($property in $frozen.files.PSObject.Properties){$path=Join-Path $private $property.Name;$sources[$path]=$property.Value.sha256}
foreach($property in $frozen.helpers.PSObject.Properties){$path=Join-Path (Join-Path $PSScriptRoot 'frozen_helpers') $property.Name;$sources[$path]=$property.Value.sha256}
foreach($name in @($sourceName,'silhouette_source.hpp','PRIVATE_SOURCE_FREEZE.json','freeze_private_sources.py','PROTOCOL.json','build_native.ps1')){
    $path=Join-Path $PSScriptRoot $name;$sources[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$flags=@($frozen.compile_flags)
$flags+="-I$OpenCV/build"
foreach($module in @('core','imgproc','highgui','imgcodecs','videoio')){$flags+="-I$OpenCV/modules/$module/include"}
$exe=Join-Path $out ($Target+'.exe')
$compileArgs=@($flags)+@($core,$source,"-L$OpenCV/build/lib",'-lopencv_world4120','-lz','-lpsapi','-o',$exe)
$manifest=[ordered]@{target=$Target;compiler=$Compiler;core_revision=$frozen.git_revision;private_core_compiled=$core;compile_arguments=$compileArgs;source_sha256=$sources;image_decodes=0;matcher_calls=0}
$manifest|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $out 'attempt_manifest.json') -Encoding UTF8
$previousErrorAction=$ErrorActionPreference
try {
    # Windows PowerShell represents native stderr warnings as ErrorRecords.
    # Preserve stderr and inspect the actual compiler exit instead of treating
    # inherited MIPP warnings as a terminating PowerShell exception.
    $ErrorActionPreference='Continue'
    & $Compiler @compileArgs 1> (Join-Path $out 'compiler_stdout.txt') 2> (Join-Path $out 'compiler_stderr.txt')
    $exit=$LASTEXITCODE
} finally {$ErrorActionPreference=$previousErrorAction}
$manifest['compiler_exit_code']=$exit
foreach($path in $sources.Keys){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sources[$path]){throw "Actual build source changed during compilation: $path"}}
if($exit -ne 0){$manifest|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $out 'failure_manifest.json') -Encoding UTF8;throw 'Native build failed; compiler evidence retained'}
$manifest['executable_sha256']=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest['scope']='Actual explicit private V11 core translation unit and private MIPP includes; no mutable production/public core compiled'
$manifest|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $out 'build_manifest.json') -Encoding UTF8
Write-Output "Built $Target from experiment-private V11 sources"
