$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path $studioRoot -Parent
$blenderExe='C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$runTag=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceRoot=Join-Path $studioRoot ('output\fresh-ui-regressions\'+$runTag)
$bootstrapScript=Join-Path $studioRoot 'tests\bootstrap_native_ui.py'
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$env:TEMP=Join-Path $workspaceRoot '.test_env\audit_tmp'
$env:TMP=$env:TEMP
$runs=@()

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

function Run-Check($name,$script,$result,$minimum,$background=$false,$demo=$false,$isolate=$true){
    $testRoot=Join-Path $workspaceRoot ('.test_env\fresh_ui_'+$runTag+'\'+$name)
    $env:BLENDER_USER_RESOURCES=Join-Path $testRoot 'blender'
    $env:TEMP=Join-Path $testRoot 'tmp'
    $env:TMP=$env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
    $isolationPath=Join-Path $testRoot 'ui_isolation.json'
    $env:LANDFALL_UI_ISOLATION_REPORT=$isolationPath
    $log=Join-Path $evidenceRoot ($name+'.log')
    $resultPath=if($result){Join-Path $studioRoot ('output\'+$result)}else{$null}
    $original=if($resultPath -and (Test-Path -LiteralPath $resultPath)){[IO.File]::ReadAllBytes($resultPath)}else{$null}
    $blenderArgs=@('--factory-startup')
    if($background){$blenderArgs+='--background'}else{$blenderArgs+='--enable-event-simulate'}
    $blenderArgs+=@('--python-exit-code','1')
    if($isolate){$blenderArgs+=@('--python',$bootstrapScript)}
    $blenderArgs+=@('--python',(Join-Path $studioRoot ('tests\'+$script)))
    if($demo){$blenderArgs+=@('--','--sculpt-demo')}
    $started=Get-Date
    & $blenderExe @blenderArgs *> $log
    $code=$LASTEXITCODE
    $entry=[ordered]@{name=$name;started=$started.ToString('o');finished=(Get-Date).ToString('o');exit=$code;log=$log;ok=($code -eq 0)}
    $content=Get-Content -LiteralPath $log -Raw
    $entry.clean_log=$content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
    $entry.ok=$entry.ok -and $entry.clean_log
    if($isolate){
        $isolation=if(Test-Path -LiteralPath $isolationPath){Get-Content -Raw -LiteralPath $isolationPath | ConvertFrom-Json}else{$null}
        $entry.isolation_fresh=$isolation -and (Get-Item -LiteralPath $isolationPath).LastWriteTime -ge $started
        $entry.qt_settings_isolated=[bool]($entry.isolation_fresh -and $isolation.ok -and ($background -or $isolation.actual_switchboard_verified))
        $entry.isolation_report=Join-Path $evidenceRoot ($name+'_isolation.json')
        if($isolation){Copy-Item -LiteralPath $isolationPath -Destination $entry.isolation_report}
        $entry.ok=$entry.ok -and $entry.qt_settings_isolated
    }
    if($resultPath){
        $data=if(Test-Path -LiteralPath $resultPath){Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json}else{$null}
        $entry.fresh=$data -and (Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started
        $entry.passed=$data.passed.Count
        $entry.failed=@(if($data.PSObject.Properties.Name -contains 'failed'){$data.failed})
        if($script -eq '..\scripts\probe_native_multires_undo_precision.py'){
            $nativeUndos=@($data.undo)+@($data.repeat_history_cycles.undo)
            $nativeRedos=@($data.redo)+@($data.repeat_history_cycles.redo)
            $entry.passed=1+$data.repeat_history_cycles.Count
            $entry.ok=$entry.ok -and $entry.fresh -and $data.ok -and -not $data.studio_imported -and $data.shape_buffers_exact -and $entry.passed -eq 10 -and @($data.no_stroke_rebuilds | Where-Object {$_.max_delta -ne 0}).Count -eq 0 -and @($nativeUndos | Where-Object {$_.max_delta -ge .000002 -or $_.rms_delta -ge .00000005}).Count -eq 0 -and @($nativeRedos | Where-Object {$_.max_delta -ge .000001}).Count -eq 0
            $entry.boundary='Blender-only numerical control, intentionally no Studio or Qt bootstrap'
        }elseif($script -eq 'test_sculpt_density_gui.py'){
            $entry.passed=if($data.ok){1}else{0}
            $entry.ok=$entry.ok -and $entry.fresh -and $data.ok -and $data.triangles -gt 200000 -and $data.redraws -gt 0 -and $data.native_tool -eq 'builtin.brush'
            $entry.triangles=$data.triangles
        }else{
            $entry.ok=$entry.ok -and $entry.fresh -and $data.failed.Count -eq 0 -and $entry.passed -ge $minimum
            if($data.PSObject.Properties.Name -contains 'ok'){$entry.ok=$entry.ok -and $data.ok}
        }
        if($data.PSObject.Properties.Name -contains 'dpr'){$entry.dpr=$data.dpr}
        elseif($data.PSObject.Properties.Name -contains 'qt_device_pixel_ratio'){$entry.dpr=$data.qt_device_pixel_ratio}
        $copy=Join-Path $evidenceRoot ($name+'.json')
        if($entry.fresh){Copy-Item -LiteralPath $resultPath -Destination $copy}
        $entry.result=$copy
        # Keep earlier frozen acceptance JSON intact; this run has its own copy.
        if($null -ne $original){[IO.File]::WriteAllBytes($resultPath,$original)}
    }elseif($script -eq 'test_phase06_headless.py'){
        $entry.ok=$entry.ok -and $content -match 'Gate 06 Headless Test Suite \(T06-1\): ALL CHECKS PASSED'
        $entry.boundary='Native background character workflow assertions; not a unittest test count'
    }else{
        $count=[regex]::Match($content,'Ran (\d+) tests?')
        $entry.tests=if($count.Success){[int]$count.Groups[1].Value}else{0}
        $entry.ok=$entry.ok -and $entry.tests -ge $minimum -and $content -match '(?m)^OK(?:\s|$)'
    }
    Write-Host ($name+': '+$(if($entry.ok){'PASS'}else{'FAIL'})+' (exit '+$code+')')
    [pscustomobject]$entry
}

foreach($scale in @(@('0.8','100',1.0),@('1','125',1.25),@('1.2','150',1.5))){
    $env:QT_SCALE_FACTOR=$scale[0]
    $env:LANDFALL_HISTORY_TAG='_fresh_'+$runTag+'_scale'+$scale[1]
    $runs+=Run-Check ('history_scale'+$scale[1]) 'test_scene_edit_history_gui.py' ('scene_edit_history_gui'+$env:LANDFALL_HISTORY_TAG+'.json') 100
    $env:LANDFALL_FULL_UX_TAG='_fresh_'+$runTag+'_scale'+$scale[1]
    $runs+=Run-Check ('full_ux_scale'+$scale[1]) 'test_full_ux_gui.py' ('full_ux_gui'+$env:LANDFALL_FULL_UX_TAG+'.json') 228
    $env:LANDFALL_UX_TEST_TAG='_fresh_'+$runTag+'_scale'+$scale[1]
    $runs+=Run-Check ('workspace_scale'+$scale[1]) 'test_sculpt_ux2_gui.py' ('sculpt_ux2_gui_results'+$env:LANDFALL_UX_TEST_TAG+'.json') 63 $false $true
    foreach($entry in $runs[-3..-1]){$entry.ok=$entry.ok -and [math]::Abs($entry.dpr-$scale[2]) -lt .01}
}
Remove-Item Env:QT_SCALE_FACTOR,Env:LANDFALL_FULL_UX_TAG,Env:LANDFALL_HISTORY_TAG,Env:LANDFALL_UX_TEST_TAG -ErrorAction SilentlyContinue
$runs+=Run-Check 'controls' 'test_controls_gui.py' 'controls_gui_results.json' 71
$runs+=Run-Check 'channel_stability' 'test_channel_stability_gui.py' 'channel_stability_gui_results.json' 13
$runs+=Run-Check 'native_channel_scrub' 'test_native_channel_scrub_gui.py' 'native_channel_scrub_extended_gui.json' 69
$env:LANDFALL_PEN_TAG='_fresh_'+$runTag
$runs+=Run-Check 'sculpt_pen' 'test_sculpt_pen_gui.py' ('sculpt_pen_gui'+$env:LANDFALL_PEN_TAG+'.json') 47 $false $true
Remove-Item Env:LANDFALL_PEN_TAG -ErrorAction SilentlyContinue
$runs+=Run-Check 'sculpt_controls' 'test_zbrush_sculpt_gui.py' 'zbrush_sculpt_gui_results.json' 93
$runs+=Run-Check 'file_lifecycle' 'test_full_ux_file_gui.py' 'full_ux_file_gui.json' 16
$runs+=Run-Check 'replacement_workflows' 'test_replacement_workflows_gui.py' 'replacement_workflows_gui.json' 78
$runs+=Run-Check 'continuous_artist_session' 'test_continuous_artist_session_gui.py' 'continuous_artist_session_gui.json' 48
$runs+=Run-Check 'native_precision_control' '..\scripts\probe_native_multires_undo_precision.py' 'native_multires_undo_precision.json' 10 $false $false $false
$env:LANDFALL_REFERENCE_TAG='_fresh_'+$runTag
$runs+=Run-Check 'sculpt_reference_gui' 'test_sculpt_reference_gui.py' ('sculpt_reference_gui'+$env:LANDFALL_REFERENCE_TAG+'.json') 56 $false $true
Remove-Item Env:LANDFALL_REFERENCE_TAG -ErrorAction SilentlyContinue
$runs+=Run-Check 'sculpt_feedback_gui' 'test_sculpt_feedback_gui.py' 'sculpt_feedback_gui_results.json' 13 $false $true
$runs+=Run-Check 'sculpt_density_gui' 'test_sculpt_density_gui.py' 'zbrush_density_results.json' 1 $false $true
$runs+=Run-Check 'controls_data' 'test_controls_data.py' 'controls_data_results.json' 122 $true
$runs+=Run-Check 'panels_data' 'test_full_ux_panels_data.py' 'full_ux_panels_data_results.json' 15 $true
$runs+=Run-Check 'character_data' 'test_phase06_headless.py' $null 5 $true
$runs+=Run-Check 'hypershade_data' 'test_phase08_headless.py' $null 6 $true
$runs+=Run-Check 'sculpt_data' 'test_zbrush_sculpt_studio.py' 'zbrush_sculpt_results.json' 77 $true
$runs+=Run-Check 'brush_memory_data' 'test_sculpt_ux2_data.py' 'sculpt_ux2_data_results.json' 10 $true
$runs+=Run-Check 'reference_data' 'test_sculpt_reference_data.py' 'sculpt_reference_data_results.json' 117 $true
$after=Source-Hashes
$stable=($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress)
$report=[ordered]@{generated=(Get-Date).ToUniversalTime().ToString('o');scope='Native UX with fresh Blender, UITK settings/presets and test-owned sculpt preferences; physical devices, clean machine and external Maya remain separate';ok=($stable -and @($runs | Where-Object {-not $_.ok}).Count -eq 0);source_stable_during_tests=$stable;runs=$runs;source_sha256=$after}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidenceRoot 'acceptance.json')
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $studioRoot 'output\fresh_ui_acceptance.json')
$runs | Select-Object name,ok,exit,passed,tests,dpr | Format-Table -AutoSize
if(-not $report.ok){exit 1}
