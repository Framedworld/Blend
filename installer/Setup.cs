// Landfall Studio installer. The application payload is a zip appended to this
// exe, followed by its 8-byte length and an 8-byte "LFSTUDIO" marker.
// Interactive by default; "/S [/D=folder]" installs silently (for testing).
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Landfall Studio Setup")]

sealed class SubStream : Stream
{
    readonly Stream inner; readonly long start, length; long position;
    public SubStream(Stream inner, long start, long length) { this.inner = inner; this.start = start; this.length = length; }
    public override bool CanRead { get { return true; } }
    public override bool CanSeek { get { return true; } }
    public override bool CanWrite { get { return false; } }
    public override long Length { get { return length; } }
    public override long Position { get { return position; } set { position = value; } }
    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count)
    {
        long left = length - position;
        if (left <= 0) return 0;
        if (count > left) count = (int)left;
        inner.Position = start + position;
        int n = inner.Read(buffer, offset, count);
        position += n;
        return n;
    }
    public override long Seek(long offset, SeekOrigin origin)
    {
        position = origin == SeekOrigin.Begin ? offset : origin == SeekOrigin.Current ? position + offset : length + offset;
        return position;
    }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] b, int o, int c) { throw new NotSupportedException(); }
}

static class Installer
{
    public static Stream OpenPayload(out FileStream exe)
    {
        exe = new FileStream(Assembly.GetExecutingAssembly().Location, FileMode.Open, FileAccess.Read, FileShare.Read);
        var trailer = new byte[16];
        exe.Position = exe.Length - 16;
        exe.Read(trailer, 0, 16);
        if (Encoding.ASCII.GetString(trailer, 8, 8) != "LFSTUDIO") throw new InvalidDataException("This installer is damaged (no payload). Please download it again.");
        long size = BitConverter.ToInt64(trailer, 0);
        return new SubStream(exe, exe.Length - 16 - size, size);
    }

    static long required = -1;

    // Unpacked size plus some room for Blender's first-start caches.
    public static long RequiredBytes()
    {
        if (required < 0)
        {
            FileStream exe;
            using (var payload = OpenPayload(out exe))
            using (exe)
            using (var zip = new ZipArchive(payload, ZipArchiveMode.Read))
            {
                long sum = 0;
                foreach (ZipArchiveEntry entry in zip.Entries) sum += entry.Length;
                required = sum + sum / 10;
            }
        }
        return required;
    }

    public static string Validate(string folder)
    {
        if (string.IsNullOrWhiteSpace(folder)) return "Choose an installation folder.";
        try { folder = Path.GetFullPath(folder); }
        catch (Exception) { return "That is not a valid folder path."; }
        bool ours = Install.IsOurs(folder);
        if (Directory.Exists(folder) && Directory.GetFileSystemEntries(folder).Length > 0 && !ours)
            return "That folder already contains other files. Choose an empty folder or the default location.";
        if (ours && Install.RunningFrom(folder).Count > 0)
            return "Landfall Studio is open. Save your work, close it, then click Install again.";
        long free = new DriveInfo(Path.GetPathRoot(folder)).AvailableFreeSpace;
        long needed = RequiredBytes() - (ours ? FolderBytes(folder) : 0);
        if (free < needed)
            return "There is not enough free disk space. Landfall Studio needs " + Megabytes(needed) + " and the drive has " + Megabytes(free) + " free.";
        return null;
    }

    public static string Megabytes(long bytes) { return (bytes / (1024 * 1024)).ToString("N0") + " MB"; }

    static long FolderBytes(string folder)
    {
        long sum = 0;
        foreach (string f in Directory.GetFiles(folder, "*", SearchOption.AllDirectories)) sum += new FileInfo(f).Length;
        return sum;
    }

    public static void Run(string folder, bool desktopShortcuts, Action<int, string> progress, bool register = true)
    {
        folder = Path.GetFullPath(folder);
        if (Install.IsOurs(folder))
        {
            progress(0, "Removing the previous version...");
            // If this fails part-way the folder still counts as ours, so trying again finishes the job.
            try { Directory.Delete(folder, true); }
            catch (IOException) { throw new IOException("Some Landfall Studio files are in use. Close Landfall Studio, then try again."); }
            catch (UnauthorizedAccessException) { throw new IOException("Some Landfall Studio files are in use. Close Landfall Studio, then try again."); }
        }
        Directory.CreateDirectory(folder);
        FileStream exe;
        using (var payload = OpenPayload(out exe))
        using (exe)
        using (var zip = new ZipArchive(payload, ZipArchiveMode.Read))
        {
            int total = zip.Entries.Count, done = 0;
            foreach (ZipArchiveEntry entry in zip.Entries)
            {
                // .NET Framework zips use backslash separators; accept either.
                string name = entry.FullName.Replace('\\', '/');
                string target = Path.GetFullPath(Path.Combine(folder, name.Replace('/', Path.DirectorySeparatorChar)));
                if (!target.StartsWith(folder, StringComparison.OrdinalIgnoreCase)) continue;
                if (name.EndsWith("/")) { Directory.CreateDirectory(target); }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    entry.ExtractToFile(target, true);
                }
                done++;
                if (done % 200 == 0 || done == total) progress(done * 100 / total, "Installing files... " + done + " / " + total);
            }
        }

        if (!register) return;  // /NOSHORTCUTS: test installs leave Start menu and Apps list alone
        progress(100, "Creating shortcuts...");
        string launcher = Path.Combine(folder, "Landfall Studio.exe");
        string menu = Shortcuts.StartMenu();
        Directory.CreateDirectory(menu);
        Shortcuts.Create(Path.Combine(menu, "Landfall Studio.lnk"), launcher, "", "Modeling, the Maya way");
        Shortcuts.Create(Path.Combine(menu, "Landfall Sculpt.lnk"), launcher, "--sculpt", "Sculpting, the ZBrush way");
        Shortcuts.Create(Path.Combine(menu, "Read Me First.lnk"), Path.Combine(folder, "Read Me First.txt"), "", "Getting started, controls and reporting problems", launcher);
        Shortcuts.Create(Path.Combine(menu, "Report a Problem.lnk"), launcher, "--report", "Save logs to your Desktop to send to the Landfall Studio team");
        Shortcuts.Create(Path.Combine(menu, "Uninstall Landfall Studio.lnk"), launcher, "--uninstall", "Remove Landfall Studio");
        if (desktopShortcuts)
        {
            string[] desk = Shortcuts.Desktop();
            Shortcuts.Create(desk[0], launcher, "", "Modeling, the Maya way");
            Shortcuts.Create(desk[1], launcher, "--sculpt", "Sculpting, the ZBrush way");
        }

        long kb = 0;
        foreach (string f in Directory.GetFiles(folder, "*", SearchOption.AllDirectories)) kb += new FileInfo(f).Length / 1024;
        using (RegistryKey key = Registry.CurrentUser.CreateSubKey(Install.UninstallKey))
        {
            key.SetValue("DisplayName", "Landfall Studio");
            key.SetValue("DisplayVersion", Install.Version);
            key.SetValue("Publisher", "Framedworld");
            key.SetValue("InstallLocation", folder);
            key.SetValue("DisplayIcon", launcher + ",0");
            key.SetValue("UninstallString", "\"" + launcher + "\" --uninstall");
            key.SetValue("QuietUninstallString", "\"" + launcher + "\" --uninstall --quiet");
            key.SetValue("EstimatedSize", (int)Math.Min(kb, int.MaxValue), RegistryValueKind.DWord);
            key.SetValue("NoModify", 1, RegistryValueKind.DWord);
            key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        }
    }

    [STAThread]
    static int Main(string[] args)
    {
        bool silent = false, register = true; string folder = Install.DefaultFolder();
        foreach (string a in args)
        {
            if (a.Equals("/S", StringComparison.OrdinalIgnoreCase)) silent = true;
            else if (a.StartsWith("/D=", StringComparison.OrdinalIgnoreCase)) folder = a.Substring(3);
            else if (a.Equals("/NOSHORTCUTS", StringComparison.OrdinalIgnoreCase)) register = false;
        }
        // A windowed exe has no console; leave the reason where testers can find it.
        string setupLog = Path.Combine(Path.GetTempPath(), "LandfallStudioSetup.log");
        if (silent)
        {
            try
            {
                string problem = Validate(folder);
                if (problem != null) { File.WriteAllText(setupLog, problem); return 2; }
                Run(folder, false, (p, s) => { }, register); return 0;
            }
            catch (Exception exc) { File.WriteAllText(setupLog, exc.ToString()); return 1; }
        }
        Application.EnableVisualStyles();
        try { RequiredBytes(); }
        catch (Exception exc)
        {
            MessageBox.Show(exc.Message, "Landfall Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        Application.Run(new SetupForm(folder));
        return 0;
    }
}

sealed class SetupForm : Form
{
    readonly TextBox folderBox = new TextBox();
    readonly CheckBox desktop = new CheckBox(), launch = new CheckBox();
    readonly Button install = new Button(), browse = new Button();
    readonly ProgressBar bar = new ProgressBar();
    readonly Label status = new Label();
    bool finished;

    public SetupForm(string folder)
    {
        Text = "Landfall Studio Setup " + Install.Version;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(560, 300); Font = new Font("Segoe UI", 9.5f);
        try { Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location); } catch { }
        var title = new Label { Text = "Landfall Studio", Font = new Font("Segoe UI Semibold", 16f), AutoSize = true, Location = new Point(20, 16) };
        var blurb = new Label { Text = "Maya-style modeling and ZBrush-style sculpting, built on Blender.\nInstalls for your Windows account only; no administrator rights needed. Blender is included.",
            AutoSize = true, Location = new Point(22, 56) };
        var where = new Label { Text = "Install to:", AutoSize = true, Location = new Point(22, 112) };
        folderBox.SetBounds(22, 134, 420, 26); folderBox.Text = folder;
        browse.Text = "Browse..."; browse.SetBounds(450, 132, 88, 28);
        browse.Click += delegate
        {
            using (var dlg = new FolderBrowserDialog { SelectedPath = folderBox.Text })
                if (dlg.ShowDialog(this) == DialogResult.OK) folderBox.Text = Path.Combine(dlg.SelectedPath, "Landfall Studio");
        };
        desktop.Text = "Add Landfall Studio and Landfall Sculpt to the desktop"; desktop.Checked = true; desktop.SetBounds(22, 170, 500, 24);
        bar.SetBounds(22, 204, 516, 18);
        status.SetBounds(22, 228, 516, 22); status.Text = "Needs " + Installer.Megabytes(Installer.RequiredBytes()) + " of disk space.";
        launch.Text = "Start Landfall Studio now"; launch.Checked = true; launch.Visible = false; launch.SetBounds(22, 258, 300, 24);
        install.Text = Install.IsOurs(folder) ? "Update" : "Install"; install.SetBounds(450, 254, 88, 30);
        install.Click += OnInstall;
        Controls.AddRange(new Control[] { title, blurb, where, folderBox, browse, desktop, bar, status, launch, install });
        AcceptButton = install;
    }

    void OnInstall(object sender, EventArgs e)
    {
        if (finished)
        {
            if (launch.Checked) Process.Start(Path.Combine(folderBox.Text, "Landfall Studio.exe"));
            Close(); return;
        }
        string problem = Installer.Validate(folderBox.Text);
        if (problem != null) { MessageBox.Show(this, problem, Text); return; }
        install.Enabled = browse.Enabled = folderBox.Enabled = desktop.Enabled = false;
        string folder = folderBox.Text; bool desk = desktop.Checked;
        var worker = new Thread(() =>
        {
            try
            {
                Installer.Run(folder, desk, (p, s) => BeginInvoke((Action)(() => { bar.Value = p; status.Text = s; })));
                BeginInvoke((Action)(() =>
                {
                    finished = true; status.Text = "Installed. Find Landfall Studio and \"Read Me First\" in the Start menu.";
                    install.Text = "Finish"; install.Enabled = true; launch.Visible = true;
                }));
            }
            catch (Exception exc)
            {
                BeginInvoke((Action)(() =>
                {
                    MessageBox.Show(this, "Installation did not finish:\n" + exc.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
                    status.Text = "Installation did not finish."; install.Enabled = browse.Enabled = folderBox.Enabled = desktop.Enabled = true;
                }));
            }
        });
        worker.IsBackground = true; worker.Start();
    }
}
