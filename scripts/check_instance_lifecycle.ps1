$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path $studioRoot -Parent
$blenderExe='C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$runTag=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceRoot=Join-Path $studioRoot ('output\instance-lifecycle\'+$runTag)
$bootstrapScript=Join-Path $studioRoot 'tests\bootstrap_native_ui.py'
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$env:QT_SCALE_FACTOR='1'
$env:LANDFALL_INSTANCE_TAG='_lifecycle_'+$runTag
$env:LANDFALL_HISTORY_TAG=$env:LANDFALL_INSTANCE_TAG
$env:LANDFALL_FULL_UX_TAG=$env:LANDFALL_INSTANCE_TAG
$env:LANDFALL_UX_TEST_TAG=$env:LANDFALL_INSTANCE_TAG
$env:LANDFALL_REFERENCE_TAG=$env:LANDFALL_INSTANCE_TAG
Remove-Item Env:LANDFALL_INSTANCE_DIRECT_HISTORY,Env:LANDFALL_INSTANCE_WINDOWS_HISTORY -ErrorAction SilentlyContinue

function Source-Hashes {
    $files=@(Get-ChildItem -LiteralPath (Join-Path $studioRoot 'landfall_studio') -Filter '*.py' -File -Recurse)
    $files+=@(Get-ChildItem -LiteralPath (Join-Path $studioRoot 'tests') -Filter 'test_*.py' -File)
    $files+=@(Get-Item -LiteralPath $PSCommandPath,$bootstrapScript,
        (Join-Path $studioRoot 'scripts\probe_native_multires_undo_precision.py'),
        (Join-Path $workspaceRoot 'upstream\blendertk\blendertk\ui_utils\qt_dock.py'),
        (Join-Path $workspaceRoot 'upstream\blendertk\blendertk\node_utils\attributes\channels\_channels.py'),
        (Join-Path $workspaceRoot 'upstream\tentacle\tentacle\slots\blender\pivot.py'))
    $hashes=[ordered]@{}
    foreach($file in $files | Sort-Object FullName){
        $hashes[[IO.Path]::GetRelativePath($workspaceRoot,$file.FullName)]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
    return $hashes
}
$before=Source-Hashes
$runs=@()

function Run-Check($name,$script,$result,$minimum,$background=$false,$demo=$false,$isolate=$true){
    $testRoot=Join-Path $workspaceRoot ('.test_env\instance_lifecycle_'+$runTag+'\'+$name)
    $env:BLENDER_USER_RESOURCES=Join-Path $testRoot 'blender'
    $env:TEMP=Join-Path $testRoot 'tmp';$env:TMP=$env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
    $isolationPath=Join-Path $testRoot 'ui_isolation.json'
    if($isolate){$env:LANDFALL_UI_ISOLATION_REPORT=$isolationPath}
    else{Remove-Item Env:LANDFALL_UI_ISOLATION_REPORT -ErrorAction SilentlyContinue}
    $log=Join-Path $evidenceRoot ($name+'.log')
    $resultPath=Join-Path $studioRoot ('output\'+$result)
    $original=if(Test-Path -LiteralPath $resultPath){[IO.File]::ReadAllBytes($resultPath)}else{$null}
    $blenderArgs=@('--factory-startup')
    if($background){$blenderArgs+='--background'}else{$blenderArgs+='--enable-event-simulate'}
    $blenderArgs+=@('--python-exit-code','1')
    if($isolate){$blenderArgs+=@('--python',$bootstrapScript)}
    $blenderArgs+=@('--python',(Join-Path $studioRoot ('tests\'+$script)))
    if($demo){$blenderArgs+=@('--','--sculpt-demo')}
    $started=Get-Date
    & $blenderExe @blenderArgs *> $log
    $code=$LASTEXITCODE
    $entry=[ordered]@{name=$name;started=$started.ToUniversalTime().ToString('o');finished=(Get-Date).ToUniversalTime().ToString('o');exit=$code;log=$log;ok=($code -eq 0)}
    $content=Get-Content -LiteralPath $log -Raw
    $entry.clean_log=$content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
    $entry.ok=$entry.ok -and $entry.clean_log
    if($isolate){
        $isolation=if(Test-Path -LiteralPath $isolationPath){Get-Content -Raw -LiteralPath $isolationPath | ConvertFrom-Json}else{$null}
        $entry.qt_settings_isolated=[bool]($isolation -and (Get-Item -LiteralPath $isolationPath).LastWriteTime -ge $started -and $isolation.ok -and ($background -or $isolation.actual_switchboard_verified))
        $entry.isolation_report=Join-Path $evidenceRoot ($name+'_isolation.json')
        if($isolation){Copy-Item -LiteralPath $isolationPath -Destination $entry.isolation_report}
        $entry.ok=$entry.ok -and $entry.qt_settings_isolated
    }
    $data=if(Test-Path -LiteralPath $resultPath){Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json}else{$null}
    $entry.fresh=[bool]($data -and (Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started)
    $entry.passed=$data.passed.Count
    $entry.failed=@(if($data.PSObject.Properties.Name -contains 'failed'){$data.failed})
    if($script -eq '..\scripts\probe_native_multires_undo_precision.py'){
        $nativeUndos=@($data.undo)+@($data.repeat_history_cycles.undo)
        $nativeRedos=@($data.redo)+@($data.repeat_history_cycles.redo)
        $entry.passed=1+$data.repeat_history_cycles.Count
        $entry.ok=$entry.ok -and $entry.fresh -and $data.ok -and -not $data.studio_imported -and $data.shape_buffers_exact -and $entry.passed -eq 10 -and @($data.no_stroke_rebuilds | Where-Object {$_.max_delta -ne 0}).Count -eq 0 -and @($nativeUndos | Where-Object {$_.max_delta -ge .000002 -or $_.rms_delta -ge .00000005}).Count -eq 0 -and @($nativeRedos | Where-Object {$_.max_delta -ge .000001}).Count -eq 0
        $entry.boundary='Blender-only numerical control; no Studio/Qt import'
    }else{
        $entry.ok=$entry.ok -and $entry.fresh -and $data.failed.Count -eq 0 -and $entry.passed -ge $minimum
        if($data.PSObject.Properties.Name -contains 'ok'){$entry.ok=$entry.ok -and $data.ok}
    }
    if($data.PSObject.Properties.Name -contains 'dpr'){$entry.dpr=$data.dpr}
    elseif($data.PSObject.Properties.Name -contains 'qt_device_pixel_ratio'){$entry.dpr=$data.qt_device_pixel_ratio}
    if($entry.Contains('dpr')){$entry.ok=$entry.ok -and [math]::Abs($entry.dpr-1.25) -lt .01}
    $entry.result=Join-Path $evidenceRoot ($name+'.json')
    if($entry.fresh){Copy-Item -LiteralPath $resultPath -Destination $entry.result}
    if($null -ne $original){[IO.File]::WriteAllBytes($resultPath,$original)}
    Write-Host ($name+': '+$(if($entry.ok){'PASS'}else{'FAIL'})+' ('+$entry.passed+' checks, exit '+$code+')')
    [pscustomobject]$entry
}

$tag=$env:LANDFALL_INSTANCE_TAG
$runs+=Run-Check 'generated_data' 'test_instance_transform_data.py' ('instance_transform_data'+$tag+'.json') 20 $true
$runs+=Run-Check 'model_duplicate' 'test_model_duplicate_gui.py' ('model_duplicate_gui'+$tag+'.json') 45
$runs+=Run-Check 'generated_gui' 'test_instance_transform_gui.py' ('instance_transform_gui'+$tag+'.json') 33
$runs+=Run-Check 'layer_goz_history' 'test_layer_goz_history_gui.py' ('layer_goz_history_gui'+$tag+'.json') 6
$runs+=Run-Check 'inspector_history' 'test_scene_edit_history_gui.py' ('scene_edit_history_gui'+$tag+'.json') 100
$runs+=Run-Check 'full_ux' 'test_full_ux_gui.py' ('full_ux_gui'+$tag+'.json') 229
$runs+=Run-Check 'controls' 'test_controls_gui.py' 'controls_gui_results.json' 71
$runs+=Run-Check 'sculpt_controls' 'test_zbrush_sculpt_gui.py' 'zbrush_sculpt_gui_results.json' 93
$runs+=Run-Check 'integrated_workflows' 'test_replacement_workflows_gui.py' 'replacement_workflows_gui.json' 78
$runs+=Run-Check 'continuous_session' 'test_continuous_artist_session_gui.py' 'continuous_artist_session_gui.json' 48
$runs+=Run-Check 'native_precision_control' '..\scripts\probe_native_multires_undo_precision.py' 'native_multires_undo_precision.json' 10 $false $false $false
$runs+=Run-Check 'workspace' 'test_sculpt_ux2_gui.py' ('sculpt_ux2_gui_results'+$tag+'.json') 63 $false $true
$runs+=Run-Check 'reference_gui' 'test_sculpt_reference_gui.py' ('sculpt_reference_gui'+$tag+'.json') 56 $false $true
$runs+=Run-Check 'sculpt_data' 'test_zbrush_sculpt_studio.py' 'zbrush_sculpt_results.json' 77 $true
$runs+=Run-Check 'reference_data' 'test_sculpt_reference_data.py' 'sculpt_reference_data_results.json' 117 $true
$after=Source-Hashes
$stable=($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress)
$previousPath=Join-Path $studioRoot 'output\fresh_ui_final_acceptance.json'
$previous=Get-Content -LiteralPath $previousPath -Raw | ConvertFrom-Json
$changed=@(foreach($property in $previous.source_sha256.PSObject.Properties){
    if($after.Contains($property.Name) -and $after[$property.Name] -ne $property.Value){
        [pscustomobject]@{path=$property.Name;before=$property.Value;after=$after[$property.Name]}
    }
})
$report=[ordered]@{generated=(Get-Date).ToUniversalTime().ToString('o');scope='Affected native matrix for generated-asset ownership, Model Duplicate/Repeat, text-key propagation and GoZ history boundary. Historical 28-suite baseline is a different production snapshot.';ok=($stable -and @($runs | Where-Object {-not $_.ok}).Count -eq 0);source_stable_during_tests=$stable;runs=$runs;source_sha256=$after;historical_baseline=$previousPath;changed_from_baseline=$changed}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidenceRoot 'acceptance.json')
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $studioRoot 'output\instance_lifecycle_acceptance.json')
$runs | Select-Object name,ok,exit,passed,dpr | Format-Table -AutoSize
if(-not $report.ok){exit 1}
