$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path $PSScriptRoot -Parent
$workspaceRoot = Split-Path $studioRoot -Parent
$blenderExe = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$testScript = Join-Path $studioRoot 'tests\test_continuous_artist_session_gui.py'
$precisionScript = Join-Path $studioRoot 'scripts\probe_native_multires_undo_precision.py'
$resultPath = Join-Path $studioRoot 'output\continuous_artist_session_gui.json'
$runTag = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceRoot = Join-Path $studioRoot 'output\continuous-artist-session'
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
$logPath = Join-Path $evidenceRoot ($runTag + '.log')
$env:BLENDER_USER_RESOURCES = Join-Path $workspaceRoot ('.test_env\artist_session_' + $runTag)
$env:TEMP = Join-Path $workspaceRoot '.test_env\audit_tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

function Source-Hashes {
    $files = @(Get-ChildItem -LiteralPath (Join-Path $studioRoot 'landfall_studio') -Filter '*.py' -File -Recurse)
    $files += @(Get-Item -LiteralPath $testScript, $precisionScript, $PSCommandPath,
        (Join-Path $workspaceRoot 'upstream\blendertk\blendertk\ui_utils\qt_dock.py'),
        (Join-Path $workspaceRoot 'upstream\blendertk\blendertk\node_utils\attributes\channels\_channels.py'),
        (Join-Path $workspaceRoot 'upstream\tentacle\tentacle\slots\blender\pivot.py'))
    $hashes = [ordered]@{}
    foreach ($file in $files | Sort-Object FullName) {
        $hashes[[IO.Path]::GetRelativePath($workspaceRoot, $file.FullName)] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
    return $hashes
}

$before = Source-Hashes
$started = Get-Date
& $blenderExe --factory-startup --enable-event-simulate --python-exit-code 1 --python $testScript *> $logPath
$processExit = $LASTEXITCODE
$precisionLog = Join-Path $evidenceRoot ($runTag + '_native_control.log')
$precisionPath = Join-Path $studioRoot 'output\native_multires_undo_precision.json'
$precisionStarted = Get-Date
$env:BLENDER_USER_RESOURCES = Join-Path $workspaceRoot ('.test_env\artist_native_control_' + $runTag)
& $blenderExe --factory-startup --enable-event-simulate --python-exit-code 1 --python $precisionScript *> $precisionLog
$precisionExit = $LASTEXITCODE
$precisionFresh = (Test-Path -LiteralPath $precisionPath) -and (Get-Item -LiteralPath $precisionPath).LastWriteTime -ge $precisionStarted
$precision = if ($precisionFresh) { Get-Content -Raw -LiteralPath $precisionPath | ConvertFrom-Json } else { $null }
$precisionClean = (Get-Content -Raw -LiteralPath $precisionLog) -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION'
$precisionCopy = Join-Path $evidenceRoot ($runTag + '_native_control.json')
if ($precisionFresh) { Copy-Item -LiteralPath $precisionPath -Destination $precisionCopy }
$nativeUndos = @($precision.undo) + @($precision.repeat_history_cycles.undo)
$nativeRedos = @($precision.redo) + @($precision.repeat_history_cycles.redo)
$precisionAccepted = $precisionExit -eq 0 -and $precisionFresh -and $precisionClean -and $precision.ok -and -not $precision.studio_imported -and $precision.shape_buffers_exact -and $precision.repeat_history_cycles.Count -eq 9 -and @($precision.no_stroke_rebuilds | Where-Object { $_.max_delta -ne 0 }).Count -eq 0 -and @($nativeUndos | Where-Object { $_.max_delta -ge 0.000002 -or $_.rms_delta -ge 0.00000005 }).Count -eq 0 -and @($nativeRedos | Where-Object { $_.max_delta -ge 0.000001 }).Count -eq 0
$after = Source-Hashes
$stable = ($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress)
$content = Get-Content -LiteralPath $logPath -Raw
$clean = $content -notmatch 'Traceback \(most recent call last\)|EXCEPTION_ACCESS_VIOLATION|\[Sculpt pen UI\] RuntimeError'
$fresh = (Test-Path -LiteralPath $resultPath) -and (Get-Item -LiteralPath $resultPath).LastWriteTime -ge $started
$data = if ($fresh) { Get-Content -Raw -LiteralPath $resultPath | ConvertFrom-Json } else { $null }
$copiedResult = Join-Path $evidenceRoot ($runTag + '.json')
if ($fresh) { Copy-Item -LiteralPath $resultPath -Destination $copiedResult }
$requiredStages = @(
    'modeling Redo restores scale before sculpting',
    'shelf enters actual Sculpt Studio',
    'layer button starts base recording',
    'native base stroke records a meaningful layer delta',
    'base stroke Undo restores the complete empty layer',
    'base stroke Redo restores all authored layer vertices',
    'held Smooth changes the recorded base form',
    'native mask stroke writes protection',
    'Mask Clear removes actual protection',
    'SubTool return retains exact base layer and recording',
    'Divide enters native Multires detail',
    'B D S selects actual subtractive DamStandard',
    'native detail stroke changes evaluated Multires surface',
    'detail preserves the entire base layer and Basis',
    'detail Undo restores evaluated pre-stroke surface',
    'detail Redo restores evaluated surface',
    'reopen preserves complete base data and target',
    'reopen preserves native high detail',
    'Shape Editor selects the actual brush-authored layer',
    'GoZ retains complete base and high-detail work'
)
$missingStages = @($requiredStages | Where-Object { $_ -notin $data.passed })
$accepted = $processExit -eq 0 -and $stable -and $clean -and $fresh -and $data.ok -and $data.failed.Count -eq 0 -and $data.passed.Count -eq 48 -and $missingStages.Count -eq 0 -and $precisionAccepted
$report = [ordered]@{
    generated = (Get-Date).ToUniversalTime().ToString('o')
    scope = 'Continuous native model/base stroke/smooth/mask/SubTool/Divide/detail/save/reopen/GoZ session; synthetic input, not physical tablet or external Maya.'
    ok = $accepted
    exit = $processExit
    fresh = $fresh
    clean_log = $clean
    source_stable_during_test = $stable
    passed = $data.passed.Count
    expected_checks = 48
    missing_required_stages = $missingStages
    failed = @($data.failed)
    dpr = $data.dpr
    log = $logPath
    result = $copiedResult
    native_precision_control = @{ok=$precisionAccepted;exit=$precisionExit;fresh=$precisionFresh;clean_log=$precisionClean;result=$precisionCopy;log=$precisionLog}
    source_sha256 = $after
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidenceRoot ($runTag + '_acceptance.json'))
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $studioRoot 'output\continuous_artist_session_acceptance.json')
[pscustomobject]$report | Select-Object ok, exit, passed, dpr, clean_log, fresh, source_stable_during_test, log | Format-List
if (-not $accepted) { exit 1 }
