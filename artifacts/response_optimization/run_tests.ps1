param(
    [string]$Compiler = 'F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OpenCV = 'D:\opencv-4.12.0'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Push-Location -LiteralPath $projectRoot
try {
    $env:PATH = "$(Split-Path -Parent $Compiler);$OpenCV\build\bin;$env:PATH"
    $env:OMP_DYNAMIC = 'FALSE'
    $env:OMP_WAIT_POLICY = 'PASSIVE'
    $buildDirectory = Join-Path $PSScriptRoot 'build'
    New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'baseline/manifest.json') -Raw | ConvertFrom-Json
    foreach($entry in $manifest.PSObject.Properties) {
        $fixture = Join-Path (Join-Path $PSScriptRoot 'baseline') $entry.Name
        if((Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
            throw "Immutable baseline hash mismatch: $fixture"
        }
    }
    $compileArguments = @('-std=c++14','-O3','-mssse3','-msse4.1','-fopenmp','-I.','-IMIPP',"-I$OpenCV/build")
    foreach($moduleName in @('core','imgproc','highgui','imgcodecs','videoio')) {
        $compileArguments += "-I$OpenCV/modules/$moduleName/include"
    }
    $results = @()
    foreach($testName in @('spread','response','pipeline','workspace','buffer')) {
        $sources = @("tests/${testName}_test.cpp")
        if($testName -eq 'workspace') { $sources += @('line2Dup.cpp','tests/reference_matcher.cpp') }
        if($testName -eq 'buffer') { $sources += @('line2Dup.cpp') }
        $executable = Join-Path $buildDirectory "${testName}_test.exe"
        $buildLog = Join-Path $buildDirectory "${testName}_build.log"
        # Windows PowerShell treats redirected native stderr warnings as error
        # records. Check the compiler exit code, while preserving its log.
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $Compiler @compileArguments @sources "-L$OpenCV/build/lib" '-lopencv_world4120' '-o' $executable *> $buildLog
        $compileExit = $LASTEXITCODE
        $ErrorActionPreference = $previousPreference
        if($compileExit -ne 0) { Get-Content -LiteralPath $buildLog -Tail 40; throw "Build failed: $testName" }
        $output = & $executable 2>&1
        if($LASTEXITCODE -ne 0) { $output | Write-Output; throw "Test failed: $testName" }
        $output | Write-Output
        $results += @{ test=$testName; passed=$true; output=($output -join "`n") }
    }
    @{ completed_at=(Get-Date -Format o); baseline_hashes_verified=$true; tests=$results } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'test_results.json') -Encoding UTF8
} finally { Pop-Location }
