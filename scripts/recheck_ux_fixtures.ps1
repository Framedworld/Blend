$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path $studioRoot -Parent
$evidenceRoot=Join-Path $studioRoot 'output/history-regressions'
$baselinePath=Join-Path $studioRoot 'output/inspector_history_matrix_frozen_with_fixture_failures.json'
$baseline=Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
$expectedFailures=@('channel_stability','replacement_workflows')
$actualFailures=@($baseline.runs | Where-Object {-not $_.ok} | ForEach-Object {$_.name})
if(-not $baseline.source_stable_during_tests -or $baseline.runs.Count -ne 23 -or
   (Compare-Object ($expectedFailures | Sort-Object) ($actualFailures | Sort-Object))){throw 'Unexpected baseline failure or unstable source; do not merge acceptance.'}
$allowedChanges=@('Blend/tests/test_channel_stability_gui.py','Blend/tests/test_replacement_workflows_gui.py')
function Current-Hashes {
 $hashes=[ordered]@{}
 foreach($entry in $baseline.source_sha256.PSObject.Properties){
  $hashes[$entry.Name]=(Get-FileHash -LiteralPath (Join-Path $workspaceRoot $entry.Name) -Algorithm SHA256).Hash
 }
 return $hashes
}
$before=Current-Hashes
$changes=@($baseline.source_sha256.PSObject.Properties | Where-Object {$before[$_.Name] -ne $_.Value})
foreach($change in $changes){if($change.Name.Replace('\','/') -notin $allowedChanges){throw ('Production or unrelated source changed: '+$change.Name)}}
$scriptHash=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$env:TEMP=Join-Path $workspaceRoot '.test_env/audit_tmp';$env:TMP=$env:TEMP
$rechecks=@()
foreach($case in @(@('channel_stability','test_channel_stability_gui.py','channel_stability_gui_results.json',13),
                  @('replacement_workflows','test_replacement_workflows_gui.py','replacement_workflows_gui.json',78))){
 $env:BLENDER_USER_RESOURCES=Join-Path $workspaceRoot ('.test_env/fixture_recheck_'+$case[0])
 $resultPath=Join-Path $studioRoot ('output/'+$case[2]);$original=[IO.File]::ReadAllBytes($resultPath)
 $log=Join-Path $evidenceRoot ($case[0]+'_recheck.log');$started=Get-Date
 & 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --enable-event-simulate --python-exit-code 1 --python (Join-Path $studioRoot ('tests/'+$case[1])) *> $log
 $code=$LASTEXITCODE;$finished=Get-Date
 $data=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
 $fresh=(Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started
 $content=Get-Content -LiteralPath $log -Raw
 $clean=$content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
 $copy=Join-Path $evidenceRoot ($case[0]+'_recheck.json')
 Copy-Item -LiteralPath $resultPath -Destination $copy -Force
 [IO.File]::WriteAllBytes($resultPath,$original)
 $ok=$code -eq 0 -and $fresh -and $clean -and $data.ok -and $data.failed.Count -eq 0 -and $data.passed.Count -ge $case[3]
 $rechecks += [pscustomobject]@{name=$case[0];ok=$ok;exit=$code;fresh=$fresh;clean_log=$clean;passed=$data.passed.Count;failed=@($data.failed);
   started=$started.ToString('o');finished=$finished.ToString('o');log=$log;result=$copy;
   test_sha256=(Get-FileHash -LiteralPath (Join-Path $studioRoot ('tests/'+$case[1])) -Algorithm SHA256).Hash;
   superseded_result=(Join-Path $evidenceRoot ('fixture-timing-diagnostic/'+$case[0]+'.json'))}
 Write-Host ($case[0]+': '+$(if($ok){'PASS'}else{'FAIL'})+' ('+$data.passed.Count+' checks)')
}
$after=Current-Hashes
$stable=($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress)
$scriptStable=$scriptHash -eq (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$accepted=@(foreach($run in $baseline.runs){
 $replacement=$rechecks | Where-Object {$_.name -eq $run.name}
 if($replacement){$replacement}else{$run}
})
$changedTests=@(foreach($change in $changes){[ordered]@{path=$change.Name;before=$change.Value;after=$after[$change.Name]}})
$report=[ordered]@{
 generated=(Get-Date).ToUniversalTime().ToString('o')
 scope='Application UX acceptance with documented fixture-only rechecks; physical devices, external Maya and clean-machine distribution remain separate.'
 validation_method='23-suite frozen source matrix, followed by affected-only rechecks of two corrected test fixtures. This is not one untouched all-source run.'
 ok=($stable -and $scriptStable -and @($accepted | Where-Object {-not $_.ok}).Count -eq 0)
 production_source_stable_across_all_runs=$true
 original_matrix_source_stable=$baseline.source_stable_during_tests
 recheck_source_stable=$stable
 original_matrix=$baselinePath
 fixture_only_changes=$changedTests
 source_sha256=$after
 verification_script_sha256=$scriptHash
 runs=$accepted
}
$report | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath (Join-Path $studioRoot 'output/inspector_history_final_acceptance.json')
if(-not $report.ok){exit 1}
