param([string]$Setup, [string]$Target)
# Silent test install (no shortcuts/registry), then start the INSTALLED launcher on
# the hidden desktop for both entry points and check what a tester relies on:
# Studio's own startup report, the session log, crash detection, the problem
# report, updating while Studio is open, recovering an interrupted update, uninstall.
$ErrorActionPreference = 'Stop'
$studio = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path $studio -Parent
if (-not $Setup) { $Setup = (Get-ChildItem (Join-Path $studio 'output\installer') -Filter 'LandfallStudioSetup-*.exe' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName }
if (-not $Target) { $Target = Join-Path $workspace '.test_env\install_test\Landfall Studio' }
if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
$reports = Join-Path $workspace '.test_env\install_test\reports'
if (Test-Path $reports) { Remove-Item $reports -Recurse -Force }
New-Item -ItemType Directory -Force -Path $reports | Out-Null
# Nobody can answer a dialog on the hidden desktop; reports must not land on the real Desktop.
$env:LANDFALL_STUDIO_NO_PROMPTS = '1'
$env:LANDFALL_STUDIO_REPORT_DIR = $reports
$profileLogs = Join-Path $env:LOCALAPPDATA 'Landfall Studio\logs'
$result = [ordered]@{ setup = $Setup; target = $Target }

function Install-Silent([string]$folder) {
    $log = Join-Path $env:TEMP 'LandfallStudioSetup.log'
    if (Test-Path $log) { Remove-Item $log -Force }
    $p = Start-Process -FilePath $Setup -ArgumentList '/S', "`"/D=$folder`"", '/NOSHORTCUTS' -Wait -PassThru
    [ordered]@{ exit = $p.ExitCode; message = $(if (Test-Path $log) { (Get-Content $log -Raw).Trim() }) }
}
function Studio-Blenders { Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object { $_.ExecutablePath -like "$Target*" } }

$t0 = Get-Date
$install = Install-Silent $Target
$result.install_exit = $install.exit
$result.install_seconds = [int]((Get-Date) - $t0).TotalSeconds
$result.installed_mb = [int]((Get-ChildItem $Target -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
if ($install.exit -ne 0) { $result.install_message = $install.message; $result | ConvertTo-Json; exit 1 }

$report = Join-Path $Target 'Blend\output\interactive_startup.json'
foreach ($mode in @('modeling', 'sculpt')) {
    if (Test-Path $report) { Remove-Item $report -Force }
    $launchArgs = if ($mode -eq 'sculpt') { '--sculpt' } else { '' }
    $since = Get-Date
    # The launcher now stays until Blender exits, so run it alongside the checks.
    $runnerArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        "`"$(Join-Path $PSScriptRoot '..\scripts\run_hidden_desktop.ps1')`"", '-Exe', "`"$(Join-Path $Target 'Landfall Studio.exe')`"",
        '-TimeoutSeconds', '400', '-DesktopName', "LandfallInstall_$mode")
    if ($launchArgs) { $runnerArgs += @('-Arguments', $launchArgs) }
    $runner = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList $runnerArgs
    # open_studio.py writes the report on open, then again once it has verified the live UI.
    $deadline = (Get-Date).AddSeconds(180); $ok = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $report) {
            try { $ok = Get-Content $report -Raw | ConvertFrom-Json } catch { }
            if ($ok -and ($ok.PSObject.Properties.Name -contains 'verified_at')) { break }
        }
        Start-Sleep -Milliseconds 500
    }
    $result["$($mode)_report"] = $ok
    $result["$($mode)_ok"] = [bool]($ok -and $ok.ok)

    $log = Get-ChildItem $profileLogs -Filter 'studio-*.log' | Where-Object { $_.LastWriteTime -ge $since } | Sort-Object LastWriteTime | Select-Object -Last 1
    $logText = ''
    if ($log) {  # still open for writing by the launcher
        $fs = [IO.FileStream]::new($log.FullName, 'Open', 'Read', 'ReadWrite, Delete')
        $logText = [IO.StreamReader]::new($fs).ReadToEnd(); $fs.Dispose()
    }
    $result["$($mode)_log_captured"] = [bool]($logText -match 'Landfall Studio 0\.' -and $logText -match 'LANDFALL_INTERACTIVE_READY')

    if ($mode -eq 'modeling') {
        # Updating while Studio is open is refused and leaves the install working.
        $busy = Install-Silent $Target
        $result.update_while_open = [ordered]@{ exit = $busy.exit; message = $busy.message;
            install_intact = (Test-Path (Join-Path $Target 'Landfall Studio.exe')) -and (Test-Path (Join-Path $Target 'blender\blender.exe')) }
        # The in-app Help > Report a Problem path, through the installed launcher.
        & (Join-Path $Target 'Landfall Studio.exe') --report --quiet | Out-Null
        Start-Sleep 3
        $zip = Get-ChildItem $reports -Filter '*.zip' | Select-Object -Last 1
        $entries = @()
        if ($zip) { Add-Type -AssemblyName System.IO.Compression.FileSystem; $z = [IO.Compression.ZipFile]::OpenRead($zip.FullName); $entries = @($z.Entries | ForEach-Object FullName); $z.Dispose() }
        $result.report_entries = $entries
        $result.report_ok = ($entries -contains 'about.txt') -and [bool]($entries | Where-Object { $_ -like 'logs/studio-*.log' }) -and ($entries -contains 'interactive_startup.json')
    }

    # Killing Blender stands in for a crash: the launcher must record it.
    Studio-Blenders | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    if (-not $runner.WaitForExit(30000)) { $runner.Kill() }
    $exitInfo = Get-Content (Join-Path $profileLogs 'last_exit.json') -Raw | ConvertFrom-Json
    $result["$($mode)_crash_recorded"] = [bool]($exitInfo.crashed -and ([datetime]$exitInfo.at) -ge $since)
    Start-Sleep 2
}

# An update interrupted part-way (files already removed) can simply be run again.
Remove-Item (Join-Path $Target 'Landfall Studio.exe') -Force
Remove-Item (Join-Path $Target 'Blend') -Recurse -Force
$resume = Install-Silent $Target
$result.resume_interrupted_update = [ordered]@{ exit = $resume.exit; message = $resume.message; restored = Test-Path (Join-Path $Target 'Landfall Studio.exe') }

# Quiet uninstall removes the folder.
& (Join-Path $Target 'Landfall Studio.exe') --uninstall --quiet
$deadline = (Get-Date).AddSeconds(90)
while ((Test-Path $Target) -and (Get-Date) -lt $deadline) { Start-Sleep 1 }
$result.uninstalled = -not (Test-Path $Target)
$result.ok = $result.modeling_ok -and $result.sculpt_ok -and $result.modeling_log_captured -and $result.sculpt_log_captured -and
    $result.modeling_crash_recorded -and $result.sculpt_crash_recorded -and $result.report_ok -and
    ($result.update_while_open.exit -eq 2) -and $result.update_while_open.install_intact -and
    ($resume.exit -eq 0) -and $result.resume_interrupted_update.restored -and $result.uninstalled
$result | ConvertTo-Json -Depth 5
if (-not $result.ok) { exit 1 }
