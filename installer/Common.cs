// Shared by the launcher and the installer.
using System;
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

    public static void Create(string path, string target, string arguments, string description)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(shellType);
        object link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
        Type t = link.GetType();
        t.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { target });
        t.InvokeMember("Arguments", BindingFlags.SetProperty, null, link, new object[] { arguments });
        t.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { Path.GetDirectoryName(target) });
        t.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { description });
        t.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { target + ",0" });
        t.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
    }

    public static void Remove()
    {
        try { if (Directory.Exists(StartMenu())) Directory.Delete(StartMenu(), true); } catch { }
        foreach (string p in Desktop()) { try { if (File.Exists(p)) File.Delete(p); } catch { } }
    }
}
