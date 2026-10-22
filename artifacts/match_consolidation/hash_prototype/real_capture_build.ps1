param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV='D:\opencv-4.12.0',
    [switch]$CpuSlotGranted
)
$ErrorActionPreference='Stop'
if(-not $CpuSlotGranted) {throw 'Parent must grant a native CPU slot before building'}
& py -3.10 (Join-Path $PSScriptRoot 'real_capture_build.py') --output $OutputDirectory --compiler $Compiler --opencv $OpenCV --cpu-slot-granted
if($LASTEXITCODE -ne 0) {throw 'Private capture build failed; preserve its evidence directory'}
