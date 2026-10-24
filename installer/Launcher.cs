// Landfall Studio launcher: starts the bundled Blender with Studio, shows a start
// window until Studio is up, keeps Blender's output in a log and offers a problem
// report if Blender closes unexpectedly.
// Usage: "Landfall Studio.exe" [--sculpt] [file.blend]  |  --report [--quiet]  |  --uninstall [--quiet]
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Reflection;
using Microsoft.Win32;

[assembly: AssemblyTitle("Landfall Studio")]

static class Launcher
{
    // Tests run on a hidden desktop where nobody can answer a dialog.
    static readonly bool NoPrompts = Environment.GetEnvironmentVariable("LANDFALL_STUDIO_NO_PROMPTS") == "1";

    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        bool quiet = NoPrompts || Array.IndexOf(args, "--quiet") >= 0;
        if (Array.IndexOf(args, "--uninstall") >= 0) return Uninstall(root, quiet);
        if (Array.IndexOf(args, "--report") >= 0) return Report.SaveAndShow(root, quiet, null) != null ? 0 : 1;

        string blender = Path.Combine(root, @"blender\blender.exe");
        string entry = Path.Combine(root, @"Blend\scripts\open_studio.py");
        string deps = Path.Combine(root, @".deps\py313");
        foreach (string required in new[] { blender, entry, Path.Combine(deps, @"PySide6\__init__.py") })
        {
            if (!File.Exists(required))
            {
                Message("Landfall Studio is incomplete:\n" + required + "\n\nPlease run the installer again.", MessageBoxIcon.Error);
                return 1;
            }
        }

        // A second double-click while Studio is still starting would open a second copy.
        bool first;
        using (var starting = new Mutex(true, @"Local\LandfallStudioStarting", out first))
        {
            if (!first) return 0;
            return Run(root, blender, entry, deps, args, starting);
        }
    }

    static int Run(string root, string blender, string entry, string deps, string[] args, Mutex starting)
    {
        // Studio keeps its own Blender profile, so the artist's Blender is untouched.
        string profile = Install.ProfileRoot();
        string temp = Path.Combine(profile, "temp");
        string logs = Path.Combine(profile, "logs");
        Directory.CreateDirectory(temp);
        Directory.CreateDirectory(logs);
        foreach (FileInfo old in new DirectoryInfo(logs).GetFiles("studio-*.log").OrderByDescending(f => f.LastWriteTimeUtc).Skip(9))
            try { old.Delete(); } catch { }

        // blender.exe is a console program: run it without a console window and keep its output.
        var psi = new ProcessStartInfo(blender);
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.RedirectStandardOutput = psi.RedirectStandardError = true;
        psi.StandardOutputEncoding = psi.StandardErrorEncoding = Encoding.UTF8;
        psi.WorkingDirectory = root;
        psi.EnvironmentVariables["TEMP"] = temp;
        psi.EnvironmentVariables["TMP"] = temp;
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";  // a crash must not lose the last lines
        psi.EnvironmentVariables["BLENDER_USER_RESOURCES"] = Path.Combine(profile, "blender");
        psi.EnvironmentVariables["LANDFALL_STUDIO_DEPS"] = deps;
        psi.EnvironmentVariables["TENTACLE_QT_DEPS"] = deps;
        psi.EnvironmentVariables["LANDFALL_STUDIO_UPSTREAM_ROOT"] = Path.Combine(root, "upstream");
        psi.EnvironmentVariables["LANDFALL_STUDIO_PROFILE"] = profile;
        psi.EnvironmentVariables["LANDFALL_STUDIO_LAUNCHER"] = Path.Combine(root, "Landfall Studio.exe");

        string blend = null;
        foreach (string a in args)
            if (a.EndsWith(".blend", StringComparison.OrdinalIgnoreCase) && File.Exists(a)) blend = a;
        bool sculpt = Array.IndexOf(args, "--sculpt") >= 0 && blend == null;
        psi.Arguments = "--factory-startup " + (blend != null ? Quote(blend) + " " : "")
            + "--python " + Quote(entry) + (sculpt ? " -- --sculpt-demo" : "");

        DateTime started = DateTime.UtcNow;
        string logPath = Path.Combine(logs, "studio-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".log");
        var log = new StreamWriter(new FileStream(logPath, FileMode.Create, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete), new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("Landfall Studio " + Install.Version + " | " + Environment.OSVersion + " | " + DateTime.Now.ToString("u"));
        log.WriteLine(Quote(blender) + " " + psi.Arguments);
        DataReceivedEventHandler write = (s, e) => { if (e.Data != null) lock (log) log.WriteLine(e.Data); };

        var blenderProcess = new Process { StartInfo = psi };
        blenderProcess.OutputDataReceived += write;
        blenderProcess.ErrorDataReceived += write;
        try { blenderProcess.Start(); }
        catch (Exception exc)
        {
            log.Dispose();
            Message("Landfall Studio could not start Blender:\n" + exc.Message, MessageBoxIcon.Error);
            return 1;
        }
        blenderProcess.BeginOutputReadLine();
        blenderProcess.BeginErrorReadLine();

        string startup = Path.Combine(root, @"Blend\output\interactive_startup.json");
        string startupError = null;
        if (!NoPrompts)
        {
            Application.EnableVisualStyles();
            var splash = new StartWindow(blenderProcess, startup, started);
            Application.Run(splash);
            startupError = splash.StartupError;
        }
        starting.ReleaseMutex();
        if (startupError != null)
            Message("Landfall Studio opened Blender, but its interface did not finish loading.\n\n"
                + "Use \"Report a Problem\" in the Start menu (Landfall Studio folder) and send us the file it saves.", MessageBoxIcon.Warning);

        blenderProcess.WaitForExit();
        blenderProcess.WaitForExit();  // the second wait drains the redirected output
        int code = blenderProcess.ExitCode;
        bool crashFile = new DirectoryInfo(temp).GetFiles("*.crash.txt").Any(f => f.LastWriteTimeUtc >= started);
        bool crashed = code != 0 || crashFile;
        lock (log)
        {
            log.WriteLine("Blender exited with code 0x" + code.ToString("X8") + (crashFile ? " (crash log written)" : ""));
            log.Dispose();
        }
        File.WriteAllText(Path.Combine(logs, "last_exit.json"), "{\"exit_code\": " + code + ", \"crashed\": " + (crashed ? "true" : "false")
            + ", \"log\": \"" + Path.GetFileName(logPath) + "\", \"at\": \"" + DateTime.Now.ToString("o") + "\"}");

        if (crashed && !NoPrompts && MessageBox.Show(
                "Landfall Studio closed unexpectedly. Sorry about that.\n\n"
                + "Save a problem report to your Desktop? It holds logs and system details, not your scene.\n\n"
                + "To get your work back, start Landfall Studio and choose File > Recover > Auto Save.",
                "Landfall Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
            Report.SaveAndShow(root, false, "Blender closed with code 0x" + code.ToString("X8"));
        return 0;
    }

    static void Message(string text, MessageBoxIcon icon)
    {
        if (NoPrompts) { Console.Error.WriteLine(text); return; }
        MessageBox.Show(text, "Landfall Studio", MessageBoxButtons.OK, icon);
    }

    public static string Quote(string s) { return "\"" + s + "\""; }

    static int Uninstall(string root, bool quiet)
    {
        if (!quiet && MessageBox.Show("Remove Landfall Studio from this computer?\n\nYour own .blend files are not touched.",
                "Uninstall Landfall Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
            return 1;
        if (Install.RunningFrom(root).Count > 0)
        {
            if (!quiet) MessageBox.Show("Landfall Studio is still open. Save your work, close it, then uninstall again.", "Uninstall Landfall Studio");
            return 1;
        }
        bool removeProfile = !quiet && MessageBox.Show("Also remove Landfall Studio's settings, logs and auto-saves?",
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

// Shown from launch until Studio reports that its interface is open.
sealed class StartWindow : Form
{
    readonly Process blender; readonly string startup; readonly DateTime started;
    readonly System.Windows.Forms.Timer poll = new System.Windows.Forms.Timer { Interval = 250 };
    public string StartupError;

    public StartWindow(Process blender, string startup, DateTime started)
    {
        this.blender = blender; this.startup = startup; this.started = started;
        Text = "Landfall Studio"; FormBorderStyle = FormBorderStyle.None; StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(420, 132); BackColor = Color.FromArgb(38, 40, 44); ForeColor = Color.Gainsboro;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        var title = new Label { Text = "Landfall Studio", Font = new Font("Segoe UI Semibold", 15f), AutoSize = true, Location = new Point(22, 18) };
        var note = new Label { Text = "Starting... the first start can take up to a minute.", Font = new Font("Segoe UI", 9.5f), AutoSize = true, Location = new Point(24, 58) };
        var bar = new ProgressBar { Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 30, Bounds = new Rectangle(24, 92, 372, 12) };
        Controls.AddRange(new Control[] { title, note, bar });
        poll.Tick += delegate { Check(); };
        poll.Start();
    }

    void Check()
    {
        if (blender.HasExited) { Close(); return; }
        try
        {
            var info = new FileInfo(startup);
            if (info.Exists && info.LastWriteTimeUtc >= started)
            {
                string text = File.ReadAllText(startup);
                if (text.Contains("\"error\"")) StartupError = text;
                if (StartupError != null || text.Contains("\"opened_at\"")) { Close(); return; }
            }
        }
        catch (IOException) { }  // Studio is still writing it
        if ((DateTime.UtcNow - started).TotalSeconds > 150) Close();
    }

    protected override void OnFormClosed(FormClosedEventArgs e) { poll.Stop(); base.OnFormClosed(e); }
}

// A zip on the Desktop that testers attach when they report a problem.
static class Report
{
    public static string SaveAndShow(string root, bool quiet, string reason)
    {
        string zip;
        try { zip = Save(root, reason); }
        catch (Exception exc)
        {
            if (!quiet) MessageBox.Show("Could not save the problem report:\n" + exc.Message, "Landfall Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return null;
        }
        if (!quiet)
        {
            Process.Start("explorer.exe", "/select," + Launcher.Quote(zip));
            MessageBox.Show("Saved \"" + Path.GetFileName(zip) + "\" to your Desktop.\n\n"
                + "Please send it to us with a few words about what you were doing.", "Landfall Studio");
        }
        return zip;
    }

    static string Save(string root, string reason)
    {
        string profile = Install.ProfileRoot();
        string desktop = Environment.GetEnvironmentVariable("LANDFALL_STUDIO_REPORT_DIR")  // tests
            ?? Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        string zipPath = Path.Combine(desktop, "Landfall Studio report " + DateTime.Now.ToString("yyyy-MM-dd HHmmss") + ".zip");
        using (var zip = ZipFile.Open(zipPath, ZipArchiveMode.Create))
        {
            var about = new StringBuilder();
            about.AppendLine("Landfall Studio " + Install.Version);
            about.AppendLine("Saved: " + DateTime.Now.ToString("u"));
            about.AppendLine("Windows: " + Environment.OSVersion + (Environment.Is64BitOperatingSystem ? " 64-bit" : ""));
            about.AppendLine("Install folder: " + root);
            if (reason != null) about.AppendLine("Reason: " + reason);
            AddText(zip, "about.txt", about.ToString());

            string logs = Path.Combine(profile, "logs");
            if (Directory.Exists(logs))
            {
                foreach (FileInfo f in new DirectoryInfo(logs).GetFiles("studio-*.log").OrderByDescending(f => f.LastWriteTimeUtc).Take(5)) AddFile(zip, "logs/" + f.Name, f.FullName);
                foreach (string name in new[] { "last_exit.json", "sysinfo.txt", "diagnostics.txt" })
                    if (File.Exists(Path.Combine(logs, name))) AddFile(zip, "logs/" + name, Path.Combine(logs, name));
            }
            string temp = Path.Combine(profile, "temp");
            if (Directory.Exists(temp))
                foreach (FileInfo f in new DirectoryInfo(temp).GetFiles("*.crash.txt")) AddFile(zip, "crash/" + f.Name, f.FullName);
            string startup = Path.Combine(root, @"Blend\output\interactive_startup.json");
            if (File.Exists(startup)) AddFile(zip, "interactive_startup.json", startup);
        }
        return zipPath;
    }

    static void AddText(ZipArchive zip, string name, string text)
    {
        using (var w = new StreamWriter(zip.CreateEntry(name).Open(), new UTF8Encoding(false))) w.Write(text);
    }

    // The current session's log is still open for writing.
    static void AddFile(ZipArchive zip, string name, string path)
    {
        try
        {
            using (var src = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            using (var dst = zip.CreateEntry(name).Open()) src.CopyTo(dst);
        }
        catch (IOException) { }
    }
}
