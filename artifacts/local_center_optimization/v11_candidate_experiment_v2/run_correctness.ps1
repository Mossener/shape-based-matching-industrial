param(
    [Parameter(Mandatory=$true)][ValidateSet('Build','Run')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$GreenEvidence,
    [ValidateSet('core','flags','lifetime')][string]$Stage='core',
    [string]$BuildDirectory='',
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0'
)
$ErrorActionPreference='Stop'
$arguments=@((Join-Path $PSScriptRoot 'run_correctness.py'),'--mode',$Mode.ToLowerInvariant(),
    '--green-evidence',$GreenEvidence,'--stage',$Stage,'--compiler',$Compiler,'--opencv',$OpenCV)
if($BuildDirectory) {$arguments+=@('--build-directory',$BuildDirectory)}
& python @arguments
if($LASTEXITCODE -ne 0) {throw 'V2 correctness build/run failed; available evidence was retained'}
