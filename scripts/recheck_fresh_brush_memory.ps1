$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path $studioRoot -Parent
$baselinePath=Join-Path $studioRoot 'output/fresh_ui_acceptance.json'
$baseline=Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
if(-not $baseline.ok -or -not $baseline.source_stable_during_tests -or $baseline.runs.Count -ne 28){throw 'Expected the completed frozen 28-suite matrix.'}
$allowedChange='Blend/tests/test_sculpt_ux2_data.py'
function Current-Hashes {
    $hashes=[ordered]@{}
    foreach($entry in $baseline.source_sha256.PSObject.Properties){
        $hashes[$entry.Name]=(Get-FileHash -LiteralPath (Join-Path $workspaceRoot $entry.Name) -Algorithm SHA256).Hash
    }
    return $hashes
}
$before=Current-Hashes
$changes=@($baseline.source_sha256.PSObject.Properties | Where-Object {$before[$_.Name] -ne $_.Value})
if($changes.Count -ne 1 -or $changes[0].Name.Replace('\','/') -ne $allowedChange){throw 'Expected only the fresh brush-memory fixture correction.'}
$scriptHash=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$runTag=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceRoot=Join-Path $studioRoot ('output/fresh-ui-regressions/brush-memory-recheck-'+$runTag)
$testRoot=Join-Path $workspaceRoot ('.test_env/fresh_brush_memory_'+$runTag)
New-Item -ItemType Directory -Path $evidenceRoot,(Join-Path $testRoot 'tmp') -Force | Out-Null
$env:BLENDER_USER_RESOURCES=Join-Path $testRoot 'blender'
$env:TEMP=Join-Path $testRoot 'tmp';$env:TMP=$env:TEMP
$env:LANDFALL_UI_ISOLATION_REPORT=Join-Path $testRoot 'ui_isolation.json'
$resultPath=Join-Path $studioRoot 'output/sculpt_ux2_data_results.json'
$original=[IO.File]::ReadAllBytes($resultPath)
$log=Join-Path $evidenceRoot 'brush_memory_data.log'
$started=Get-Date
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --python-exit-code 1 --python (Join-Path $studioRoot 'tests/bootstrap_native_ui.py') --python (Join-Path $studioRoot 'tests/test_sculpt_ux2_data.py') *> $log
$code=$LASTEXITCODE
$finished=Get-Date
$data=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
$fresh=(Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started
$copy=Join-Path $evidenceRoot 'brush_memory_data.json'
Copy-Item -LiteralPath $resultPath -Destination $copy
[IO.File]::WriteAllBytes($resultPath,$original)
$isolation=Get-Content -LiteralPath $env:LANDFALL_UI_ISOLATION_REPORT -Raw | ConvertFrom-Json
$isolationFresh=(Get-Item -LiteralPath $env:LANDFALL_UI_ISOLATION_REPORT).LastWriteTime -ge $started
$isolationCopy=Join-Path $evidenceRoot 'brush_memory_data_isolation.json'
Copy-Item -LiteralPath $env:LANDFALL_UI_ISOLATION_REPORT -Destination $isolationCopy
$clean=(Get-Content -LiteralPath $log -Raw) -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
$expectedPreferences=Join-Path $testRoot 'sculpt_preferences.json'
$preferencesMatch=[IO.Path]::GetFullPath($data.preferences_path) -eq [IO.Path]::GetFullPath($expectedPreferences)
$ok=$code -eq 0 -and $fresh -and $clean -and $data.failed.Count -eq 0 -and $data.passed.Count -eq 12 -and $isolationFresh -and $isolation.ok -and $isolation.background -and $data.preferences_file_existed_before -eq $false -and $preferencesMatch -and $data.passed -contains 'fresh preference file starts absent' -and $data.passed -contains 'fresh favorites start in approved order' -and $data.passed -contains 'favorites persist explicit pin order'
$recheck=[pscustomobject]@{name='brush_memory_data';ok=$ok;exit=$code;fresh=$fresh;clean_log=$clean;qt_settings_isolated=[bool]($isolationFresh -and $isolation.ok);passed=$data.passed.Count;failed=@($data.failed);started=$started.ToString('o');finished=$finished.ToString('o');log=$log;result=$copy;isolation_report=$isolationCopy;preferences_path=$data.preferences_path;preferences_file_existed_before=$data.preferences_file_existed_before;superseded_result=($baseline.runs | Where-Object {$_.name -eq 'brush_memory_data'}).result}
$after=Current-Hashes
$stable=($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress)
$scriptStable=$scriptHash -eq (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$accepted=@(foreach($run in $baseline.runs){if($run.name -eq 'brush_memory_data'){$recheck}else{$run}})
$report=[ordered]@{
    generated=(Get-Date).ToUniversalTime().ToString('o')
    scope='Native UX with fresh Blender and UITK stores, test-owned sculpt preferences, and a verified absent-file favorite-persistence recheck; physical devices, clean machine, GPU window capture and external Maya remain separate.'
    validation_method='Frozen 28-suite matrix plus one affected-only test-fixture recheck. Existing ten brush-memory assertions retained; two fresh-start assertions added. This is not one untouched all-source run.'
    ok=($stable -and $scriptStable -and @($accepted | Where-Object {-not $_.ok}).Count -eq 0)
    production_source_stable_across_all_runs=$true
    original_matrix_source_stable=$baseline.source_stable_during_tests
    recheck_source_stable=$stable
    original_matrix=$baselinePath
    fixture_only_changes=@([ordered]@{path=$changes[0].Name;before=$changes[0].Value;after=$after[$changes[0].Name]})
    source_sha256=$after
    verification_script_sha256=$scriptHash
    runs=$accepted
}
$report | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath (Join-Path $evidenceRoot 'acceptance.json')
$report | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath (Join-Path $studioRoot 'output/fresh_ui_final_acceptance.json')
Write-Host ('brush_memory_data: '+$(if($report.ok){'PASS'}else{'FAIL'})+' ('+$data.passed.Count+' checks; exit '+$code+')')
if(-not $report.ok){exit 1}
