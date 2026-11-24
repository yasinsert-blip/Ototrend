using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class Launcher : Form {
    const string AppUrl = "http://127.0.0.1:8765";
    readonly string root;
    readonly Label state = new Label { AutoSize = false, Height = 38, Dock = DockStyle.Top, TextAlign = ContentAlignment.MiddleLeft };
    readonly Button start = new Button { Text = "Programı Başlat", Width = 155, Height = 38 };
    readonly Button stop = new Button { Text = "Programı Kapat", Width = 155, Height = 38 };
    readonly Button open = new Button { Text = "Yönetim Ekranını Aç", Width = 170, Height = 38 };
    readonly Timer refreshTimer = new Timer { Interval = 2000 };
    bool refreshing;

    Launcher(string installRoot) {
        root = installRoot;
        Text = "OtoTrend AI — Kontrol Merkezi";
        Width = 510;
        Height = 205;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;

        var title = new Label { Text = "OtoTrend AI", Font = new Font(Font.FontFamily, 15, FontStyle.Bold), AutoSize = false, Height = 35, Dock = DockStyle.Top, TextAlign = ContentAlignment.MiddleLeft };
        var note = new Label { Text = "Bu pencereyi kapatmak arka plandaki haber taramasını durdurmaz.", AutoSize = false, Height = 30, Dock = DockStyle.Bottom, TextAlign = ContentAlignment.MiddleLeft, ForeColor = Color.DimGray };
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 53, FlowDirection = FlowDirection.LeftToRight, Padding = new Padding(0, 7, 0, 0) };
        buttons.Controls.Add(start);
        buttons.Controls.Add(stop);
        buttons.Controls.Add(open);
        Controls.Add(note);
        Controls.Add(buttons);
        Controls.Add(state);
        Controls.Add(title);
        Padding = new Padding(18, 12, 18, 12);

        start.Click += async (sender, eventArgs) => await StartApplication();
        stop.Click += (sender, eventArgs) => RequestStop(true);
        open.Click += (sender, eventArgs) => Process.Start(AppUrl);
        refreshTimer.Tick += async (sender, eventArgs) => await RefreshState();
        Shown += async (sender, eventArgs) => { refreshTimer.Start(); await RefreshState(); };
    }

    static bool IsRunning() {
        try {
            var request = (HttpWebRequest)WebRequest.Create(AppUrl + "/api/health");
            request.Timeout = 900;
            request.ReadWriteTimeout = 900;
            using (var response = (HttpWebResponse)request.GetResponse())
            using (var reader = new StreamReader(response.GetResponseStream())) {
                return response.StatusCode == HttpStatusCode.OK && reader.ReadToEnd().Contains("\"status\":\"ok\"");
            }
        } catch {
            return false;
        }
    }

    async Task RefreshState() {
        if (refreshing) return;
        refreshing = true;
        bool running = await Task.Run(() => IsRunning());
        refreshing = false;
        state.Text = running ? "Durum: Çalışıyor — haber taraması arka planda etkin." : "Durum: Kapalı";
        state.ForeColor = running ? Color.FromArgb(20, 110, 50) : Color.Firebrick;
        start.Enabled = !running;
        stop.Enabled = running;
        open.Enabled = running;
    }

    string ReleasePath() {
        var json = new JavaScriptSerializer();
        var pointer = json.Deserialize<Dictionary<string, string>>(File.ReadAllText(Path.Combine(root, "current.json")));
        byte[] raw = Convert.FromBase64String(pointer["manifest"]);
        using (var rsa = new RSACryptoServiceProvider()) {
            rsa.PersistKeyInCsp = false;
            using (var reader = new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("public-key.xml"))) rsa.FromXmlString(reader.ReadToEnd());
            if (!rsa.VerifyData(raw, CryptoConfig.MapNameToOID("SHA256"), Convert.FromBase64String(pointer["signature"]))) throw new Exception("Sürüm imzası geçersiz.");
        }
        dynamic data = json.DeserializeObject(Encoding.UTF8.GetString(raw));
        string hash = data["components"]["application"]["sha256"];
        if (!Regex.IsMatch(hash, "^[0-9a-f]{64}$")) throw new Exception("Geçersiz sürüm.");
        return Path.Combine(root, "versions", "application-" + hash);
    }

    async Task StartApplication() {
        if (await Task.Run(() => IsRunning())) return;
        try {
            string release = ReleasePath();
            string launcher = Path.Combine(release, "desktop", "launcher.py");
            string python = Path.Combine(release, "runtime", "pythonw.exe");
            if (!File.Exists(launcher) || !File.Exists(python)) throw new Exception("Kurulum dosyaları eksik.");
            File.Delete(Path.Combine(root, "data", "stop.request"));
            Process.Start(new ProcessStartInfo(python, "\"" + launcher + "\" \"" + root.TrimEnd('\\') + "\"") { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = root });
            state.Text = "Durum: Başlatılıyor...";
            state.ForeColor = Color.DarkGoldenrod;
            start.Enabled = false;
            await Task.Delay(1400);
            await RefreshState();
        } catch (Exception error) {
            MessageBox.Show(error.Message, "OtoTrend AI");
        }
    }

    void RequestStop(bool showMessage) {
        try {
            Directory.CreateDirectory(Path.Combine(root, "data"));
            File.WriteAllText(Path.Combine(root, "data", "stop.request"), "stop");
            state.Text = "Durum: Kapatma bekleniyor; devam eden işler güvenle tamamlanacak.";
            state.ForeColor = Color.DarkGoldenrod;
            start.Enabled = false;
            stop.Enabled = false;
            if (showMessage) MessageBox.Show("Kapatma istendi. Devam eden işler tamamlandıktan sonra OtoTrend kapanacak.", "OtoTrend AI");
        } catch (Exception error) {
            MessageBox.Show(error.Message, "OtoTrend AI");
        }
    }

    [STAThread] static void Main(string[] args) {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        if (args.Length == 1 && args[0] == "--stop") {
            Directory.CreateDirectory(Path.Combine(root, "data"));
            File.WriteAllText(Path.Combine(root, "data", "stop.request"), "stop");
            MessageBox.Show("Kapatma istendi. Devam eden işler tamamlandıktan sonra OtoTrend kapanacak.", "OtoTrend AI");
            return;
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Launcher(root));
    }
}
