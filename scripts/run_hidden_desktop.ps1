param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [string[]]$Arguments = @(),
    [string]$Log,
    [int]$TimeoutSeconds = 900,
    [string]$DesktopName = 'LandfallStudioTests'
)
# Runs a GUI process on a separate, never-shown Windows desktop so native GUI
# suites cannot take over the artist's mouse, keyboard or screen.
$ErrorActionPreference = 'Stop'
# Children must not inject OS mouse/keyboard input: it would reach the
# visible desktop, not this hidden one.
$env:LANDFALL_NO_OS_INPUT = '1'
# Flush Python output as it happens, so a hung run still leaves a readable log.
$env:PYTHONUNBUFFERED = '1'
if (-not ('HiddenDesktop' -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HiddenDesktop {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public struct STARTUPINFO { public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError; }
    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public int dwProcessId, dwThreadId; }
    [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern IntPtr CreateDesktop(string name, IntPtr device, IntPtr devmode, int flags, uint access, IntPtr sa);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool CloseDesktop(IntPtr h);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool CreateProcess(string app, string cmd, IntPtr pa, IntPtr ta, bool inherit, uint flags,
        IntPtr env, string cwd, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll")] public static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll")] public static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll")] public static extern bool TerminateProcess(IntPtr h, uint code);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
'@
}
$desktop = [HiddenDesktop]::CreateDesktop($DesktopName, [IntPtr]::Zero, [IntPtr]::Zero, 0, 0x10000000, [IntPtr]::Zero)
if ($desktop -eq [IntPtr]::Zero) { throw "CreateDesktop failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
function Quote([string]$a) { if ($a -match '[\s"]') { '"' + ($a -replace '"','\"') + '"' } else { $a } }
$inner = (Quote $Exe) + ' ' + (($Arguments | ForEach-Object { Quote $_ }) -join ' ')
# cmd.exe redirects the child's output; it runs on the hidden desktop too.
$comspec = Join-Path $env:SystemRoot 'System32\cmd.exe'
$app = if ($Log) { $comspec } else { $Exe }
$cmd = if ($Log) { '"' + $comspec + '" /d /s /c "' + $inner + ' > ' + (Quote $Log) + ' 2>&1"' } else { $inner }
$si = New-Object HiddenDesktop+STARTUPINFO
$si.cb = [Runtime.InteropServices.Marshal]::SizeOf($si)
$si.lpDesktop = 'winsta0\' + $DesktopName
$pi = New-Object HiddenDesktop+PROCESS_INFORMATION
if (-not [HiddenDesktop]::CreateProcess($app, $cmd, [IntPtr]::Zero, [IntPtr]::Zero, $false, 0x08000000, [IntPtr]::Zero, (Get-Location).Path, [ref]$si, [ref]$pi)) {
    [HiddenDesktop]::CloseDesktop($desktop) | Out-Null
    throw "CreateProcess failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}
$waited = [HiddenDesktop]::WaitForSingleObject($pi.hProcess, [uint32]($TimeoutSeconds * 1000))
if ($waited -ne 0) {
    # Kill the whole tree: cmd.exe and the Blender it started.
    & taskkill.exe /T /F /PID $pi.dwProcessId 2>$null | Out-Null
    [HiddenDesktop]::TerminateProcess($pi.hProcess, 124) | Out-Null; Start-Sleep 1
}
$code = 0; [HiddenDesktop]::GetExitCodeProcess($pi.hProcess, [ref]$code) | Out-Null
[HiddenDesktop]::CloseHandle($pi.hProcess) | Out-Null
[HiddenDesktop]::CloseHandle($pi.hThread) | Out-Null
[HiddenDesktop]::CloseDesktop($desktop) | Out-Null
exit [int]$code
