param([string[]]$Checks=@('pen','sculpt','native_scrub'))
$ErrorActionPreference='Stop'
$studioRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path $studioRoot -Parent
$exe='C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$evidence=Join-Path $studioRoot 'output\history-regressions'
$env:TEMP=Join-Path $workspaceRoot '.test_env\audit_tmp'
$env:TMP=$env:TEMP
$runs=@()
foreach($check in $Checks){
    $demo=$false
    switch($check){
        'pen' {$script='tests\test_sculpt_pen_gui.py';$result='sculpt_pen_gui_history_recovery.json';$minimum=47;$demo=$true;$env:LANDFALL_PEN_TAG='_history_recovery'}
        'sculpt' {$script='tests\test_zbrush_sculpt_gui.py';$result='zbrush_sculpt_gui_results.json';$minimum=93}
        'native_scrub' {$script='scripts\probe_native_channel_scrub_gui.py';$result='native_channel_scrub_gui.json';$minimum=11}
        default {throw "Unknown check: $check"}
    }
    $env:BLENDER_USER_RESOURCES=Join-Path $workspaceRoot ('.test_env\history_recovery_'+$check)
    $path=Join-Path $studioRoot ('output\'+$result)
    $original=if(Test-Path -LiteralPath $path){[IO.File]::ReadAllBytes($path)}else{$null}
    $log=Join-Path $evidence ($check+'_recovery.log')
    $blenderArgs=@('--factory-startup','--enable-event-simulate','--python-exit-code','1','--python',(Join-Path $studioRoot $script))
    if($demo){$blenderArgs+=@('--','--sculpt-demo')}
    $started=Get-Date
    & $exe @blenderArgs *> $log
    $code=$LASTEXITCODE
    $data=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $fresh=(Get-Item -LiteralPath $path).LastWriteTime -ge $started
    $content=Get-Content -LiteralPath $log -Raw
    $clean=$content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
    $copy=Join-Path $evidence ($check+'_recovery.json')
    Copy-Item -LiteralPath $path -Destination $copy -Force
    $entry=[ordered]@{name=$check;started=$started.ToString('o');finished=(Get-Date).ToString('o');exit=$code;passed=$data.passed.Count;failed=@($data.failed);fresh=$fresh;clean_log=$clean;result=$copy;log=$log;ok=($code -eq 0 -and $fresh -and $clean -and $data.failed.Count -eq 0 -and $data.passed.Count -ge $minimum)}
    if($data.PSObject.Properties.Name -contains 'ok'){$entry.ok=$entry.ok -and $data.ok}
    $runs+=[pscustomobject]$entry
    if($null -ne $original){[IO.File]::WriteAllBytes($path,$original)}
    Remove-Item Env:LANDFALL_PEN_TAG -ErrorAction SilentlyContinue
    $runs | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $evidence 'recovery_runs.json')
}
$runs | Select-Object name,ok,exit,passed | Format-Table -AutoSize
if(@($runs | Where-Object {-not $_.ok}).Count){exit 1}
