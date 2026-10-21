param(
    [string]$Compiler='F:\mysys2\ucrt64\bin\g++.exe',
    [string]$OutputDirectory='artifacts/quality_coverage/run_20261021_helper'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
if(Test-Path -LiteralPath $OutputDirectory){throw 'Output directory must be new; preserve previous evidence'}
$env:PATH="$(Split-Path -Parent $Compiler);$env:PATH"
$names=@('coverage_helper.hpp','coverage_nms.hpp','coverage_test.cpp')
$before=[ordered]@{}
foreach($name in $names+@('run_tests.ps1')){$before[$name]=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant()}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
function Invoke-Native([string]$File,[string[]]$Arguments,[string]$Prefix) {
    $start=New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName=$File
    $start.Arguments=($Arguments | ForEach-Object {'"'+($_ -replace '"','\"')+'"'}) -join ' '
    $start.UseShellExecute=$false;$start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $process=New-Object System.Diagnostics.Process;$process.StartInfo=$start
    [void]$process.Start()
    $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    [IO.File]::WriteAllText($Prefix+'_stdout.txt',$stdout.Result)
    [IO.File]::WriteAllText($Prefix+'_stderr.txt',$stderr.Result)
    return @{exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result}
}
$flags=@('-std=c++14','-O2','-Wall','-Wextra','-Werror')
$cases=New-Object System.Collections.Generic.List[object]
function Run-Case([string]$Name,[string]$SourceRoot,[bool]$ExpectPass,[string]$MutateFile='', [string]$Old='', [string]$New='') {
    $directory=Join-Path $OutputDirectory $Name
    $source=Join-Path $directory 'source'
    New-Item -ItemType Directory -Path $source -Force | Out-Null
    foreach($fileName in $names){Copy-Item -LiteralPath (Join-Path $SourceRoot $fileName) -Destination (Join-Path $source $fileName)}
    if($MutateFile){
        $path=Join-Path $source $MutateFile;$text=[IO.File]::ReadAllText($path)
        if(($text.Split([string[]]@($Old),[StringSplitOptions]::None).Count-1) -ne 1){throw "Mutation must have one exact target: $Name"}
        [IO.File]::WriteAllText($path,$text.Replace($Old,$New),(New-Object Text.UTF8Encoding($false)))
    }
    $exe=Join-Path $directory 'coverage_test.exe'
    $compile=Invoke-Native $Compiler ($flags+@((Join-Path $source 'coverage_test.cpp'),'-o',$exe)) (Join-Path $directory 'compile')
    if($compile.exit_code -ne 0){throw "Compile failed for $Name : $($compile.stderr)"}
    if($compile.stderr.Length -ne 0){throw "Compiler diagnostics for $Name : $($compile.stderr)"}
    $test=Invoke-Native ([IO.Path]::GetFullPath($exe)) @() (Join-Path $directory 'test')
    if(($test.exit_code -eq 0) -ne $ExpectPass){throw "Unexpected test outcome for $Name : $($test.stdout) $($test.stderr)"}
    $hashes=[ordered]@{}
    foreach($fileName in $names){$hashes[$fileName]=(Get-FileHash -LiteralPath (Join-Path $source $fileName) -Algorithm SHA256).Hash.ToLowerInvariant()}
    $item=[ordered]@{name=$Name;expected=if($ExpectPass){'PASS'}else{'semantic test failure'};compile_exit=$compile.exit_code;
        test_exit=$test.exit_code;stdout=$test.stdout;stderr=$test.stderr;source_sha256=$hashes;
        executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()}
    if($ExpectPass){$item['metrics']=$test.stdout | ConvertFrom-Json}
    if($MutateFile){$item['mutation']=@{file=$MutateFile;old=$Old;new=$New}}
    $cases.Add($item)
    Write-Output "$Name : expected=$($item.expected), exit=$($test.exit_code) $($test.stdout)$($test.stderr)"
}
$started=Get-Date -Format o
Run-Case 'red_missing_support' (Join-Path $PSScriptRoot 'red_missing_support') $false
Run-Case 'green' $PSScriptRoot $true
Run-Case 'red_wrap_removed' $PSScriptRoot $false 'coverage_helper.hpp' '(distance<=1 || distance==7)' '(distance<=1)'
Run-Case 'red_radius_reduced' $PSScriptRoot $false 'coverage_helper.hpp' 'const int effective_radius=radius;' 'const int effective_radius=std::max(0,radius-1);'
Run-Case 'red_balanced_replaced' $PSScriptRoot $false 'coverage_helper.hpp' 'result.balanced/=double(result.occupied_cells);' 'result.balanced=double(result.supported)/double(result.points);'
Run-Case 'red_oob_denominator' $PSScriptRoot $false 'coverage_helper.hpp' 'result.unweighted=double(result.supported)/double(result.points);' 'result.unweighted=double(result.supported)/double(std::max(std::size_t(1),result.in_bounds));'
Run-Case 'red_nms_boundary' $PSScriptRoot $false 'coverage_nms.hpp' 'box_iou(candidate.box,k.candidate.box)>nms' 'box_iou(candidate.box,k.candidate.box)>=nms'
Run-Case 'red_lazy_reject_inverted' $PSScriptRoot $false 'coverage_nms.hpp' 'if(!passes(coverage,threshold))' 'if(passes(coverage,threshold))'
foreach($name in $before.Keys){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before[$name]){throw "Source changed during validation: $name"}}
$compilerVersion=Invoke-Native $Compiler @('--version') (Join-Path $OutputDirectory 'compiler_version')
$report=[ordered]@{status='PASS';started_at=$started;completed_at=(Get-Date -Format o);git_revision=((& git rev-parse HEAD).Trim());
    compiler=$Compiler;compiler_sha256=(Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash.ToLowerInvariant();
    compiler_version=$compilerVersion.stdout;flags=$flags;source_sha256=$before;sources_unchanged=$true;dataset_access=$false;
    scope='Synthetic helper and isolated NMS correctness only; no matcher integration, accuracy or latency claim';cases=$cases.ToArray()}
$report|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $OutputDirectory 'validation.json') -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run_tests.ps1') -Destination (Join-Path $OutputDirectory 'run_tests.ps1')
Write-Output 'PASS synthetic helper + independent oracles + seven expected RED failures'
