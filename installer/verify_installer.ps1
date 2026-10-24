param([string]$Setup, [string]$Target)
# Silent test install (no shortcuts/registry), then start the INSTALLED launcher on
# the hidden desktop and wait for Studio's own startup report, for both entry points.
$ErrorActionPreference = 'Stop'
$studio = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path $studio -Parent
if (-not $Setup) { $Setup = (Get-ChildItem (Join-Path $studio 'output\installer') -Filter 'LandfallStudioSetup-*.exe' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName }
if (-not $Target) { $Target = Join-Path $workspace '.test_env\install_test\Landfall Studio' }
if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
$result = [ordered]@{ setup = $Setup; target = $Target }

$t0 = Get-Date
$p = Start-Process -FilePath $Setup -ArgumentList '/S', "`"/D=$Target`"", '/NOSHORTCUTS' -Wait -PassThru
$result.install_exit = $p.ExitCode
$result.install_seconds = [int]((Get-Date) - $t0).TotalSeconds
$result.installed_mb = [int]((Get-ChildItem $Target -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
if ($p.ExitCode -ne 0) { $result | ConvertTo-Json; exit 1 }

$report = Join-Path $Target 'Blend\output\interactive_startup.json'
foreach ($mode in @('modeling', 'sculpt')) {
    if (Test-Path $report) { Remove-Item $report -Force }
    $launchArgs = if ($mode -eq 'sculpt') { @('--sculpt') } else { @() }
    # The launcher returns at once; Blender inherits the hidden desktop.
    & (Join-Path $PSScriptRoot '..\scripts\run_hidden_desktop.ps1') -Exe (Join-Path $Target 'Landfall Studio.exe') -Arguments $launchArgs -TimeoutSeconds 30 -LingerSeconds 15 | Out-Null
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
    Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object { $_.ExecutablePath -like "$Target*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep 2
}

# Quiet uninstall removes the folder.
& (Join-Path $Target 'Landfall Studio.exe') --uninstall --quiet
Start-Sleep 10
$result.uninstalled = -not (Test-Path $Target)
$result.ok = $result.modeling_ok -and $result.sculpt_ok -and $result.uninstalled
$result | ConvertTo-Json -Depth 5
if (-not $result.ok) { exit 1 }
