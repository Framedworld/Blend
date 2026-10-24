param([string]$Setup, [string]$Target)
# Clicks through the installer's own window, then watches the launcher's start
# window and crash prompt, all on a hidden desktop. Windows are found and
# pressed with window messages: no OS mouse/keyboard input, no screen capture.
# The interactive install registers a Start menu folder and an Apps entry for
# this Windows user; the quiet uninstall at the end removes them again.
$ErrorActionPreference = 'Stop'
$studio = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path $studio -Parent
if (-not $Setup) { $Setup = (Get-ChildItem (Join-Path $studio 'output\installer') -Filter 'LandfallStudioSetup-*.exe' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName }
if (-not $Target) { $Target = Join-Path $workspace '.test_env\dialog_test\Landfall Studio' }
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LandfallStudio'
if (Test-Path $uninstallKey) { throw 'Landfall Studio is installed for this user; this check would replace its shortcuts. Uninstall it first.' }
if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
Remove-Item Env:LANDFALL_STUDIO_NO_PROMPTS -ErrorAction SilentlyContinue

if (-not ('DesktopWindows' -as [type])) {
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
// user32 only accepts window handles from the calling thread's own desktop,
// so every call runs on a short-lived thread attached to the hidden desktop.
public static class DesktopWindows {
    delegate bool EnumProc(IntPtr hwnd, IntPtr lp);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr OpenDesktop(string name, int flags, bool inherit, uint access);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr h);
    [DllImport("user32.dll")] static extern bool SetThreadDesktop(IntPtr h);
    [DllImport("user32.dll")] static extern bool EnumDesktopWindows(IntPtr desk, EnumProc fn, IntPtr lp);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc fn, IntPtr lp);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, StringBuilder l);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, string l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, int msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public static string Desktop = "";

    static T On<T>(Func<IntPtr, T> fn) {
        T value = default(T); Exception error = null;
        var t = new Thread(() => {
            IntPtr d = OpenDesktop(Desktop, 0, false, 0x01FF);
            if (d == IntPtr.Zero) return;
            try { if (SetThreadDesktop(d)) value = fn(d); }
            catch (Exception e) { error = e; }
            finally { CloseDesktop(d); }
        });
        t.Start(); t.Join();
        if (error != null) throw error;
        return value;
    }
    static string TextOf(IntPtr h) {
        int n = (int)SendMessage(h, 0x000E, IntPtr.Zero, IntPtr.Zero);   // WM_GETTEXTLENGTH
        var sb = new StringBuilder(n + 1); SendMessage(h, 0x000D, (IntPtr)(n + 1), sb); return sb.ToString();
    }
    static string ClassOf(IntPtr h) { var sb = new StringBuilder(256); GetClassName(h, sb, 256); return sb.ToString(); }
    // Each row: handle, class, text, process id.
    public static List<object[]> TopLevel() {
        return On(d => {
            var rows = new List<object[]>();
            EnumDesktopWindows(d, (h, lp) => {
                if (IsWindowVisible(h)) { uint pid; GetWindowThreadProcessId(h, out pid); rows.Add(new object[] { h, ClassOf(h), TextOf(h), pid }); }
                return true; }, IntPtr.Zero);
            return rows; });
    }
    public static List<object[]> Children(IntPtr parent) {
        return On(d => {
            var rows = new List<object[]>();
            EnumChildWindows(parent, (h, lp) => { rows.Add(new object[] { h, ClassOf(h), TextOf(h), (int)SendMessage(h, 0x00F0, IntPtr.Zero, IntPtr.Zero) }); return true; }, IntPtr.Zero);
            return rows; });
    }
    public static bool SetText(IntPtr h, string text) { return On(d => { SendMessage(h, 0x000C, IntPtr.Zero, text); return true; }); }   // WM_SETTEXT
    public static bool Click(IntPtr h) { return On(d => PostMessage(h, 0x00F5, IntPtr.Zero, IntPtr.Zero)); }                          // BM_CLICK
}
'@
}

$desk = 'LandfallDialogs'
[DesktopWindows]::Desktop = $desk
function Windows { foreach ($r in [DesktopWindows]::TopLevel()) { [pscustomobject]@{ h = $r[0]; class = $r[1]; title = $r[2]; pid = $r[3] } } }
function Controls($h) { foreach ($r in [DesktopWindows]::Children($h)) { [pscustomobject]@{ h = $r[0]; class = $r[1]; text = $r[2]; checked = ($r[3] -eq 1) } } }
function Wait-For([scriptblock]$probe, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) { $v = & $probe; if ($v) { return $v }; Start-Sleep -Milliseconds 250 }
    return $null
}
$result = [ordered]@{ setup = $Setup }

# 1. The installer window.
$runner = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    "`"$(Join-Path $studio 'scripts\run_hidden_desktop.ps1')`"", '-Exe', "`"$Setup`"", '-TimeoutSeconds', '600', '-LingerSeconds', '240', '-DesktopName', $desk)
$setupWin = Wait-For { Windows | Where-Object { $_.title -like 'Landfall Studio Setup*' } | Select-Object -First 1 } 60
if (-not $setupWin) { $result.setup_window = $false; $result | ConvertTo-Json; exit 1 }
$controls = Controls $setupWin.h
$result.setup_title = $setupWin.title
$result.setup_texts = @($controls | Where-Object { $_.text } | ForEach-Object text)
$folderBox = $controls | Where-Object { $_.class -like '*EDIT*' } | Select-Object -First 1
$desktopBox = $controls | Where-Object { $_.text -like 'Add Landfall Studio*desktop*' } | Select-Object -First 1
$installButton = $controls | Where-Object { $_.text -eq 'Install' } | Select-Object -First 1
$result.default_folder = $folderBox.text
[DesktopWindows]::SetText($folderBox.h, $Target) | Out-Null
[DesktopWindows]::Click($desktopBox.h) | Out-Null   # keep the real Desktop clean
Start-Sleep -Milliseconds 300
$t0 = Get-Date
[DesktopWindows]::Click($installButton.h) | Out-Null
$finish = Wait-For { $c = Controls $setupWin.h; if ($c | Where-Object { $_.text -eq 'Finish' }) { $c } } 240
$result.install_seconds = [int]((Get-Date) - $t0).TotalSeconds
$result.finish_texts = @($finish | Where-Object { $_.text } | ForEach-Object text)
$result.start_menu = @(Get-ChildItem (Join-Path ([Environment]::GetFolderPath('Programs')) 'Landfall Studio') -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object BaseName)
$result.apps_entry = Test-Path $uninstallKey
$result.desktop_shortcut_created = Test-Path (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Landfall Studio.lnk')

# 2. Finish with "Start Landfall Studio now" checked: the start window shows, then closes once Studio is up.
$report = Join-Path $Target 'Blend\output\interactive_startup.json'
[DesktopWindows]::Click(($finish | Where-Object { $_.text -eq 'Finish' } | Select-Object -First 1).h) | Out-Null
$clicked = Get-Date
$splash = Wait-For { Windows | Where-Object { $_.title -eq 'Landfall Studio' -and $_.class -like 'WindowsForms*' } | Select-Object -First 1 } 30
$result.start_window_shown = [bool]$splash
$result.start_window_texts = if ($splash) { @(Controls $splash.h | Where-Object { $_.text } | ForEach-Object text) } else { @() }
$opened = Wait-For { if ((Test-Path $report) -and (Get-Content $report -Raw) -match 'opened_at') { Get-Date } } 180
$gone = Wait-For { if (-not (Windows | Where-Object { $splash -and $_.h -eq $splash.h })) { Get-Date } } 30
$result.studio_opened_seconds = if ($opened) { [int]($opened - $clicked).TotalSeconds } else { $null }
$result.start_window_closed_after_open = [bool]($opened -and $gone -and $gone -ge $opened.AddSeconds(-1))
if ($splash) {
    $blenders = @(Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object { $_.ExecutablePath -like "$Target*" }).Count
    $result.blender_processes = $blenders
}
$result.console_windows = @(Windows | Where-Object { $_.class -eq 'ConsoleWindowClass' }).Count

# 3. Blender ends abnormally: the launcher offers a problem report. Answer No.
Start-Sleep 25   # let Studio finish verifying its UI
Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object { $_.ExecutablePath -like "$Target*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
$prompt = Wait-For { Windows | Where-Object { $_.title -eq 'Landfall Studio' -and $_.class -eq '#32770' } | Select-Object -First 1 } 30
$result.crash_prompt_shown = [bool]$prompt
if ($prompt) {
    $pc = Controls $prompt.h
    $result.crash_prompt_text = ($pc | Where-Object { $_.class -eq 'Static' -and $_.text } | ForEach-Object text) -join ' '
    [DesktopWindows]::Click(($pc | Where-Object { $_.text -match '^&?No$' } | Select-Object -First 1).h) | Out-Null
}
$launcherGone = Wait-For { if (-not (Get-CimInstance Win32_Process -Filter "Name='Landfall Studio.exe'" | Where-Object { $_.ExecutablePath -like "$Target*" })) { $true } } 30
$result.launcher_exited = [bool]$launcherGone

# 4. Clean up: the quiet uninstall removes the folder, Start menu folder and Apps entry.
& (Join-Path $Target 'Landfall Studio.exe') --uninstall --quiet
$removed = Wait-For { if (-not (Test-Path $Target)) { $true } } 90
$result.uninstalled = [bool]$removed -and -not (Test-Path $uninstallKey) -and -not (Test-Path (Join-Path ([Environment]::GetFolderPath('Programs')) 'Landfall Studio'))
if (-not $runner.HasExited) { $runner.Kill() }

$result.ok = $result.start_menu.Count -ge 5 -and $result.apps_entry -and -not $result.desktop_shortcut_created -and
    $result.start_window_shown -and $result.start_window_closed_after_open -and $result.console_windows -eq 0 -and
    $result.crash_prompt_shown -and $result.launcher_exited -and $result.uninstalled
$result | ConvertTo-Json -Depth 4
if (-not $result.ok) { exit 1 }
