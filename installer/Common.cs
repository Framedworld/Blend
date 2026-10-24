// Shared by the launcher and the installer.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;

static class Install
{
    public const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\LandfallStudio";
    public const string Version = "0.9.0-beta.1";

    public static string ProfileRoot()
    {
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Landfall Studio");
    }

    // Top-level entries of an install. A folder holding only these is ours, even
    // after an interrupted update removed some of them.
    static readonly string[] Shipped = { "Landfall Studio.exe", "blender", "Blend", "upstream", ".deps", "Read Me First.txt", "QUICK_START.md", "THIRD_PARTY_NOTICES.txt" };

    public static bool IsOurs(string folder)
    {
        if (!Directory.Exists(folder)) return false;
        string[] entries = Directory.GetFileSystemEntries(folder);
        if (entries.Length == 0) return false;
        foreach (string e in entries)
            if (Array.FindIndex(Shipped, n => n.Equals(Path.GetFileName(e), StringComparison.OrdinalIgnoreCase)) < 0) return false;
        return true;
    }

    // Studio processes started from this folder (other than the caller).
    public static List<string> RunningFrom(string folder)
    {
        string prefix = Path.GetFullPath(folder).TrimEnd('\\') + "\\";
        var found = new List<string>();
        int self = Process.GetCurrentProcess().Id;
        foreach (string name in new[] { "blender", "blender-launcher", "Landfall Studio" })
            foreach (Process p in Process.GetProcessesByName(name))
            {
                try { if (p.Id != self && p.MainModule.FileName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) found.Add(p.ProcessName); }
                catch { }  // exited, or not ours to inspect
            }
        return found;
    }

    public static string DefaultFolder()
    {
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Programs\Landfall Studio");
    }
}

static class Shortcuts
{
    public static string StartMenu()
    {
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Landfall Studio");
    }

    public static string[] Desktop()
    {
        string d = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        return new[] { Path.Combine(d, "Landfall Studio.lnk"), Path.Combine(d, "Landfall Sculpt.lnk") };
    }

    public static void Create(string path, string target, string arguments, string description, string icon = null)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(shellType);
        object link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
        Type t = link.GetType();
        t.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { target });
        t.InvokeMember("Arguments", BindingFlags.SetProperty, null, link, new object[] { arguments });
        t.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { Path.GetDirectoryName(target) });
        t.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { description });
        t.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { (icon ?? target) + ",0" });
        t.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
    }

    public static void Remove()
    {
        try { if (Directory.Exists(StartMenu())) Directory.Delete(StartMenu(), true); } catch { }
        foreach (string p in Desktop()) { try { if (File.Exists(p)) File.Delete(p); } catch { } }
    }
}
