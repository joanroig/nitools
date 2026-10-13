// NITools bootstrap, GPL-3.0. Uses the Windows-provided .NET Framework only.
// No Microsoft runtime DLL or redistributable installer is embedded.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Launcher
{
    internal const string DownloadUrl = "https://aka.ms/vc14/vc_redist.x64.exe";
    internal const string HelpUrl = "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist";
    internal static readonly string Root = AppDomain.CurrentDomain.BaseDirectory;

    internal static bool RuntimeReady()
    {
        string[] lines = File.ReadAllLines(Path.Combine(Root, "runtime-requirements.txt"));
        if (lines.Length == 0) throw new IOException("The runtime requirements file is empty. Extract the complete ZIP again.");
        foreach (string line in lines)
        {
            string[] parts = line.Split('|');
            if (parts.Length != 2 || !Regex.IsMatch(parts[0], @"\A[a-zA-Z0-9_]+\.dll\z"))
                throw new IOException("Invalid runtime requirements. Extract the complete ZIP again.");
            string path = Path.Combine(Environment.SystemDirectory, parts[0]);
            if (!File.Exists(path)) return false;
            FileVersionInfo v = FileVersionInfo.GetVersionInfo(path);
            if (new Version(v.FileMajorPart, v.FileMinorPart, v.FileBuildPart, v.FilePrivatePart) < new Version(parts[1]))
                return false;
        }
        return true;
    }

    internal static void StartApp()
    {
        string executable = Path.Combine(Root, "NIToolsApp.exe");
        if (!File.Exists(executable)) throw new IOException("NIToolsApp.exe is missing. Extract the complete ZIP again.");
        Process.Start(new ProcessStartInfo(executable) { WorkingDirectory = Root, UseShellExecute = false });
    }

    // Windows verifies the signature and certificate chain. HTTPS alone is not
    // treated as sufficient authorization to execute the downloaded file.
    internal static bool VerifyInstaller(string path)
    {
        string command = "$s=Get-AuthenticodeSignature -LiteralPath $env:NITOOLS_RUNTIME_INSTALLER; " +
            "if($s.Status -eq 'Valid' -and $s.SignerCertificate.GetNameInfo(" +
            "[System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) " +
            "-eq 'Microsoft Corporation'){exit 0}; exit 1";
        var start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe"),
            "-NoProfile -NonInteractive -Command \"" + command + "\"") {
            UseShellExecute = false, CreateNoWindow = true
        };
        start.EnvironmentVariables["NITOOLS_RUNTIME_INSTALLER"] = path;
        // A launch from PowerShell 7 can inherit its incompatible module paths.
        // Let Windows PowerShell resolve its own built-in signature cmdlet.
        start.EnvironmentVariables.Remove("PSModulePath");
        using (Process process = Process.Start(start))
        {
            if (!process.WaitForExit(60000)) { process.Kill(); return false; }
            return process.ExitCode == 0;
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            // Read-only diagnostic used by the package qualification check.
            if (args.Length == 1 && args[0] == "--check-runtime") return RuntimeReady() ? 0 : 2;
            if (args.Length == 1 && args[0] == "--runtime-setup") { Application.Run(new SetupForm()); return 0; }
            if (RuntimeReady()) StartApp();
            else Application.Run(new SetupForm());
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "NITools could not start", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}

internal sealed class SetupForm : Form
{
    private readonly Label status = new Label();
    private readonly ProgressBar progress = new ProgressBar();
    private readonly Button install = new Button();
    private WebClient download;
    private bool busy;
    private bool installing;

    internal SetupForm()
    {
        Text = "Set up NITools";
        ClientSize = new Size(500, 280);
        Font = new Font("Segoe UI", 10);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        var title = new Label { Text = "One requirement before you start", Font = new Font(Font, FontStyle.Bold),
            Location = new Point(24, 22), Size = new Size(452, 28) };
        var description = new Label { Text = "NITools needs Microsoft's Visual C++ runtime.\n\n" +
            "Download it directly from Microsoft and open its installer. Windows may ask you to approve installation.",
            Location = new Point(24, 60), Size = new Size(452, 85) };
        status.SetBounds(24, 150, 452, 38);
        progress.SetBounds(24, 192, 452, 12);
        install.Text = "Download and install";
        install.SetBounds(270, 220, 206, 36);
        install.Click += async delegate { await InstallRuntime(); };
        var help = new LinkLabel { Text = "Microsoft download page", Location = new Point(24, 228), AutoSize = true };
        help.LinkClicked += delegate { Process.Start(new ProcessStartInfo(Launcher.HelpUrl) { UseShellExecute = true }); };
        Controls.AddRange(new Control[] { title, description, status, progress, install, help });
        FormClosing += delegate(object sender, FormClosingEventArgs e) {
            if (busy) { e.Cancel = true; if (!installing && download != null) download.CancelAsync(); }
        };
    }

    private async Task InstallRuntime()
    {
        string folder = Path.Combine(Path.GetTempPath(), "NITools-runtime-" + Guid.NewGuid().ToString("N"));
        string installer = Path.Combine(folder, "vc_redist.x64.exe");
        busy = true;
        install.Enabled = false;
        try
        {
            Directory.CreateDirectory(folder);
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            using (download = new WebClient())
            {
                download.DownloadProgressChanged += delegate(object sender, DownloadProgressChangedEventArgs e) {
                    progress.Value = e.ProgressPercentage;
                    status.Text = "Downloading from Microsoft... " + e.ProgressPercentage + "%";
                };
                await download.DownloadFileTaskAsync(new Uri(Launcher.DownloadUrl), installer);
            }
            download = null;
            status.Text = "Verifying Microsoft's digital signature...";
            if (!await Task.Run(() => Launcher.VerifyInstaller(installer)))
                throw new IOException("The Microsoft signature could not be verified. The installer was not run. Try again or use the official download page.");
            installing = true;
            status.Text = "Complete Microsoft's installer, then return here.";
            int exitCode = await Task.Run(() => {
                using (Process process = Process.Start(new ProcessStartInfo(installer, "/install /norestart") {
                    UseShellExecute = true, Verb = "runas"
                })) { process.WaitForExit(); return process.ExitCode; }
            });
            if (exitCode != 0 && exitCode != 3010 && exitCode != 1641)
                throw new IOException("Installation did not complete (code " + exitCode + "). You can retry or install from Microsoft's download page.");
            if (exitCode == 3010 || exitCode == 1641)
            {
                status.Text = "Microsoft requests a restart. Restart Windows, then open NITools again.";
                return;
            }
            if (!Launcher.RuntimeReady()) throw new IOException("The required runtime is still unavailable. Restart Windows after installation and try again.");
            Launcher.StartApp();
            busy = false;
            Close();
        }
        catch (Exception error) { status.Text = "Setup did not finish. You can try again."; MessageBox.Show(this, error.Message, "Runtime setup", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        finally
        {
            download = null;
            busy = installing = false;
            install.Enabled = true;
            try { if (File.Exists(installer)) File.Delete(installer); if (Directory.Exists(folder)) Directory.Delete(folder); }
            catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }
}
