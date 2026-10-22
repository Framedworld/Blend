$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$blenderExe='C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$env:TEMP=Join-Path (Split-Path $studioRoot -Parent) '.test_env\audit_tmp'
$env:TMP=$env:TEMP
$report=@()
function Run-StudioCheck($name,$script,$result,$demo=$false,$background=$false){
    $env:BLENDER_USER_RESOURCES=Join-Path (Split-Path $studioRoot -Parent) ('.test_env\ux2_'+$name)
    $arguments=@('--factory-startup')
    if($background){$arguments+='--background'}else{$arguments+='--enable-event-simulate'}
    $arguments+=@('--python',(Join-Path $studioRoot ('tests\'+$script)))
    if($demo){$arguments+=@('--','--sculpt-demo')}
    $started=Get-Date
    & $blenderExe @arguments *> (Join-Path $studioRoot ('output\ux2_qa_'+$name+'.log'))
    $code=$LASTEXITCODE
    $path=Join-Path $studioRoot ('output\'+$result)
    $data=Get-Content $path -Raw | ConvertFrom-Json
    $fresh=(Get-Item $path).LastWriteTime -gt $started
    $ok=$code -eq 0 -and $fresh -and $data.failed.Count -eq 0
    if($null -ne $data.ok){$ok=$ok -and $data.ok}
    [pscustomobject]@{name=$name;ok=$ok;exit_code=$code;fresh=$fresh;passed=$data.passed.Count;failed=$data.failed.Count;qt_dpr=$data.qt_device_pixel_ratio}
}
# The installed display's native Qt DPR is 1.25. Ratios produce actual 1/1.25/1.5.
foreach($scale in @(@('0.8','100'),@('1','125'),@('1.2','150'))){
    $env:QT_SCALE_FACTOR=$scale[0]
    $env:LANDFALL_UX_TEST_TAG='_scale'+$scale[1]
    $report+=Run-StudioCheck ('scale'+$scale[1]) 'test_sculpt_ux2_gui.py' ('sculpt_ux2_gui_results_scale'+$scale[1]+'.json') $true
}
Remove-Item Env:QT_SCALE_FACTOR -ErrorAction SilentlyContinue
Remove-Item Env:LANDFALL_UX_TEST_TAG -ErrorAction SilentlyContinue
$report+=Run-StudioCheck 'sculpt_regression' 'test_zbrush_sculpt_gui.py' 'zbrush_sculpt_gui_results.json'
$report+=Run-StudioCheck 'maya_regression' 'test_controls_gui.py' 'controls_gui_results.json'
$report+=Run-StudioCheck 'density' 'test_sculpt_density_gui.py' 'zbrush_density_results.json' $true
$report+=Run-StudioCheck 'brush_memory' 'test_sculpt_ux2_data.py' 'sculpt_ux2_data_results.json' $false $true
$report | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $studioRoot 'output\sculpt_ux2_qa_summary.json')
$report | Format-Table -AutoSize
if($report.Where({-not $_.ok}).Count){exit 1}
