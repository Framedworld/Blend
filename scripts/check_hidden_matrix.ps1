param([string[]]$Only = @(), [int]$TimeoutSeconds = 1200)
# Runs the native Studio suites without touching the artist's screen: GUI
# suites on a hidden Windows desktop (scripts\run_hidden_desktop.ps1), data
# suites in Blender background mode. OS mouse clicks are disabled there
# (LANDFALL_NO_OS_INPUT); those routes are reported as skipped, not passed.
$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path $PSScriptRoot -Parent
$workspaceRoot = Split-Path $studioRoot -Parent
$blenderExe = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$runTag = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidence = Join-Path $studioRoot ('output\hidden-matrix\' + $runTag)
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$bootstrap = Join-Path $studioRoot 'tests\bootstrap_native_ui.py'
$tag = '_hidden_' + $runTag
foreach ($name in 'LANDFALL_INSTANCE_TAG','LANDFALL_HISTORY_TAG','LANDFALL_FULL_UX_TAG','LANDFALL_UX_TEST_TAG','LANDFALL_REFERENCE_TAG') {
    Set-Item -Path ('Env:' + $name) -Value $tag
}
$env:QT_SCALE_FACTOR = '1'
$env:LANDFALL_NO_OS_INPUT = '1'

# name, script, gui, demo, result json (relative to output, {tag} replaced)
$suites = @(
    @('maya_extrude', 'test_maya_extrude_headless.py', $false, $false, $null),
    @('maya_menus', 'test_maya_menus_headless.py', $false, $false, $null),
    @('maya_group', 'test_maya_group_headless.py', $false, $false, $null),
    @('sculptris_pro', 'test_sculptris_pro_headless.py', $false, $false, $null),
    @('maya_ascii', 'test_maya_ascii_headless.py', $false, $false, $null),
    @('report_problem', 'test_report_problem_headless.py', $false, $false, $null),
    @('imm', 'test_imm_headless.py', $false, $false, $null),
    @('controls_data', 'test_controls_data.py', $false, $false, $null),
    @('phase01', 'test_phase01_headless.py', $false, $false, $null),
    @('phase02', 'test_phase02_headless.py', $false, $false, $null),
    @('phase03', 'test_phase03_headless.py', $false, $false, $null),
    @('phase04', 'test_phase04_headless.py', $false, $false, $null),
    @('phase05', 'test_phase05_headless.py', $false, $false, $null),
    @('phase06', 'test_phase06_headless.py', $false, $false, $null),
    @('phase08', 'test_phase08_headless.py', $false, $false, $null),
    @('phase09', 'test_phase09_headless.py', $false, $false, $null),
    @('phase10', 'test_phase10_headless.py', $false, $false, $null),
    @('phase11', 'test_phase11_headless.py', $false, $false, $null),
    @('commands_data', 'test_full_ux_commands_data.py', $false, $false, $null),
    @('panels_data', 'test_full_ux_panels_data.py', $false, $false, $null),
    @('generated_data', 'test_instance_transform_data.py', $false, $false, 'instance_transform_data{tag}.json'),
    @('sculpt_data', 'test_zbrush_sculpt_studio.py', $false, $false, 'zbrush_sculpt_results.json'),
    @('reference_data', 'test_sculpt_reference_data.py', $false, $false, 'sculpt_reference_data_results.json'),
    @('native_duplicate', 'test_native_duplicate_gui.py', $true, $false, 'native_duplicate_gui{tag}.json'),
    @('model_duplicate', 'test_model_duplicate_gui.py', $true, $false, 'model_duplicate_gui{tag}.json'),
    @('generated_gui', 'test_instance_transform_gui.py', $true, $false, 'instance_transform_gui{tag}.json'),
    @('inspector_history', 'test_scene_edit_history_gui.py', $true, $false, 'scene_edit_history_gui{tag}.json'),
    @('controls', 'test_controls_gui.py', $true, $false, 'controls_gui_results.json'),
    @('imm_gui', 'test_imm_gui.py', $true, $false, 'imm_gui{tag}.json'),
    @('imm_undo_gui', 'test_imm_undo_gui.py', $true, $true, 'imm_undo_gui{tag}.json'),
    @('full_ux', 'test_full_ux_gui.py', $true, $false, 'full_ux_gui{tag}.json'),
    @('sculpt_controls', 'test_zbrush_sculpt_gui.py', $true, $false, 'zbrush_sculpt_gui_results.json'),
    @('integrated_workflows', 'test_replacement_workflows_gui.py', $true, $false, 'replacement_workflows_gui.json'),
    @('continuous_session', 'test_continuous_artist_session_gui.py', $true, $false, 'continuous_artist_session_gui.json'),
    @('workspace', 'test_sculpt_ux2_gui.py', $true, $true, 'sculpt_ux2_gui_results{tag}.json')
)
$runs = @()
foreach ($suite in $suites) {
    $name, $script, $gui, $demo, $result = $suite
    if ($Only.Count -and $Only -notcontains $name) { continue }
    $testRoot = Join-Path $workspaceRoot ('.test_env\hidden_' + $runTag + '\' + $name)
    $env:BLENDER_USER_RESOURCES = Join-Path $testRoot 'blender'
    $env:TEMP = Join-Path $testRoot 'tmp'; $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    $env:LANDFALL_UI_ISOLATION_REPORT = Join-Path $testRoot 'ui_isolation.json'
    $log = Join-Path $evidence ($name + '.log')
    $resultPath = if ($result) { Join-Path $studioRoot ('output\' + $result.Replace('{tag}', $tag)) } else { $null }
    $original = if ($resultPath -and (Test-Path -LiteralPath $resultPath)) { [IO.File]::ReadAllBytes($resultPath) } else { $null }
    $bargs = @('--factory-startup')
    $bargs += if ($gui) { '--enable-event-simulate' } else { '--background' }
    $bargs += @('--python-exit-code', '1', '--python', $bootstrap, '--python', (Join-Path $studioRoot ('tests\' + $script)))
    if ($demo) { $bargs += @('--', '--sculpt-demo') }
    $started = Get-Date
    # Background suites also start on the hidden desktop, so no process this
    # matrix launches can ever appear on the artist's screen.
    & (Join-Path $PSScriptRoot 'run_hidden_desktop.ps1') -Exe $blenderExe -Arguments $bargs -Log $log -TimeoutSeconds $TimeoutSeconds
    $code = $LASTEXITCODE
    $content = [string]$(if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Raw })
    $entry = [ordered]@{ name = $name; exit = $code; gui_hidden = $gui; log = $log }
    $entry.clean_log = $content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION'
    $ok = ($code -eq 0) -and $entry.clean_log
    if ($resultPath) {
        $fresh = (Test-Path -LiteralPath $resultPath) -and (Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started
        $entry.fresh_result = $fresh
        if ($fresh) {
            $data = Get-Content -Raw -LiteralPath $resultPath | ConvertFrom-Json
            $entry.passed = @($data.passed).Count
            $failures = @(@($data.failed) | Where-Object { $null -ne $_ } | ForEach-Object {
                $text = if ($_ -is [string]) { $_ } else { $_ | ConvertTo-Json -Compress -Depth 4 }
                $text.Substring(0, [Math]::Min(400, $text.Length)) })
            $entry.failed = $failures
            $ok = $ok -and ($failures.Count -eq 0)
            if ($data.PSObject.Properties.Name -contains 'ok') { $ok = $ok -and [bool]$data.ok }
            Copy-Item -LiteralPath $resultPath -Destination (Join-Path $evidence ($name + '.json'))
        } else { $ok = $false }
        # Leave earlier fixed-name acceptance files exactly as they were.
        if ($null -ne $original) { [IO.File]::WriteAllBytes($resultPath, $original) }
    } else {
        $count = [regex]::Match($content, 'Ran (\d+) tests?')
        $entry.tests = if ($count.Success) { [int]$count.Groups[1].Value } else { 0 }
        $ok = $ok -and (($content -match '(?m)^OK(?:\s|$)') -or ($content -match 'ALL CHECKS PASSED') -or ($content -match '"status": "PASS"') -or ($content -match '_HEADLESS_PASS|HEADLESS SUITE PASSED|\[T0[0-9]-1\] PASS') -or
            ($content -match '_RESULT:\{' -and $content -match '"failed": \[\]' -and $content -notmatch '"ok": false|"crash"'))
    }
    $entry.ok = $ok
    Write-Host ("{0,-22} {1}  exit={2} passed={3}" -f $name, $(if ($ok) { 'PASS' } else { 'FAIL' }), $code, $(if ($entry.Contains('passed')) { $entry.passed } else { $entry.tests }))
    $runs += [pscustomobject]$entry
}
$summary = [ordered]@{ run = $runTag; ok = -not ($runs | Where-Object { -not $_.ok }); hidden_desktop = $true;
    os_input = 'disabled (LANDFALL_NO_OS_INPUT); native OS click routes reported skipped'; runs = $runs }
$summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $evidence 'summary.json')
Write-Host ('SUMMARY ' + $(if ($summary.ok) { 'PASS' } else { 'FAIL' }) + ' -> ' + (Join-Path $evidence 'summary.json'))
