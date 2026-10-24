// Landfall Studio launcher: starts the bundled Blender with Studio, no console.
// Usage: "Landfall Studio.exe" [--sculpt] [file.blend]   |   --uninstall [--quiet]
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Landfall Studio")]
[assembly: AssemblyProduct("Landfall Studio")]
[assembly: AssemblyVersion("0.9.0.1")]

static class Launcher
{
    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        if (Array.IndexOf(args, "--uninstall") >= 0) return Uninstall(root, Array.IndexOf(args, "--quiet") >= 0);

        string blender = Path.Combine(root, @"blender\blender.exe");
        string entry = Path.Combine(root, @"Blend\scripts\open_studio.py");
        string deps = Path.Combine(root, @".deps\py313");
        foreach (string required in new[] { blender, entry, Path.Combine(deps, @"PySide6\__init__.py") })
        {
            if (!File.Exists(required))
            {
                MessageBox.Show("Landfall Studio is incomplete:\n" + required + "\n\nPlease reinstall it.",
                    "Landfall Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        // Studio keeps its own Blender profile, so the artist's Blender is untouched.
        string profile = Install.ProfileRoot();
        string temp = Path.Combine(profile, "temp");
        Directory.CreateDirectory(temp);
        var psi = new ProcessStartInfo(blender);
        psi.UseShellExecute = false;
        psi.WorkingDirectory = root;
        psi.EnvironmentVariables["TEMP"] = temp;
        psi.EnvironmentVariables["TMP"] = temp;
        psi.EnvironmentVariables["BLENDER_USER_RESOURCES"] = Path.Combine(profile, "blender");
        psi.EnvironmentVariables["LANDFALL_STUDIO_DEPS"] = deps;
        psi.EnvironmentVariables["TENTACLE_QT_DEPS"] = deps;
        psi.EnvironmentVariables["LANDFALL_STUDIO_UPSTREAM_ROOT"] = Path.Combine(root, "upstream");
        psi.EnvironmentVariables["LANDFALL_STUDIO_PROFILE"] = profile;

        string blend = null;
        foreach (string a in args)
            if (a.EndsWith(".blend", StringComparison.OrdinalIgnoreCase) && File.Exists(a)) blend = a;
        bool sculpt = Array.IndexOf(args, "--sculpt") >= 0 && blend == null;
        psi.Arguments = "--factory-startup " + (blend != null ? Quote(blend) + " " : "")
            + "--python " + Quote(entry) + (sculpt ? " -- --sculpt-demo" : "");
        try { Process.Start(psi); }
        catch (Exception exc)
        {
            MessageBox.Show("Landfall Studio could not start Blender:\n" + exc.Message,
                "Landfall Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }

    static string Quote(string s) { return "\"" + s + "\""; }

    static int Uninstall(string root, bool quiet)
    {
        if (!quiet && MessageBox.Show("Remove Landfall Studio from this computer?\n\nYour own .blend files are not touched.",
                "Uninstall Landfall Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
            return 1;
        bool removeProfile = !quiet && MessageBox.Show("Also remove Landfall Studio's settings and preferences?",
                "Uninstall Landfall Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
        Shortcuts.Remove();
        try { Registry.CurrentUser.DeleteSubKeyTree(Install.UninstallKey, false); } catch { }
        if (removeProfile) { try { Directory.Delete(Install.ProfileRoot(), true); } catch { } }
        // The running launcher lives in the folder; delete it once this process exits.
        var cmd = new ProcessStartInfo("cmd.exe", "/d /c timeout /t 2 /nobreak >nul & rmdir /s /q " + Quote(root.TrimEnd('\\')));
        cmd.CreateNoWindow = true; cmd.UseShellExecute = false;
        Process.Start(cmd);
        if (!quiet) MessageBox.Show("Landfall Studio has been removed.", "Uninstall Landfall Studio");
        return 0;
    }
}
