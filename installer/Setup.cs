using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Text;
class Setup : Form {
    TextBox output = new TextBox { Multiline=true, ReadOnly=true, ScrollBars=ScrollBars.Vertical, Dock=DockStyle.Fill };
    Button install = new Button { Text="Kur", Dock=DockStyle.Bottom, Height=45 };
    CheckBox accept = new CheckBox { Text="Gemma kullanım koşullarını ve kullanım kısıtlarını kabul ediyorum.", Dock=DockStyle.Top, Height=45 };
    Button terms = new Button { Text="Lisans ve kullanım koşullarını oku", Dock=DockStyle.Top, Height=35 };
    string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"OtoTrendAI");
    bool busy;
    Setup() {
        Text="OtoTrend AI — Çevrimdışı Kurulum"; Width=740; Height=520;
        Controls.Add(output); Controls.Add(terms); Controls.Add(accept); Controls.Add(install);
        output.Text="Kurulum: " + root + "\r\nTüm paket parçaları Setup.exe ile aynı klasörde olmalı.\r\nMevcut haber ve kişisel ayarlar bu pakette bulunmaz.\r\n";
        terms.Click += delegate { using(var reader = new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("terms.txt"))) { var form=new Form { Text="Gemma lisansı ve kullanım kısıtları", Width=800,Height=600 }; form.Controls.Add(new TextBox { Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill,Text=reader.ReadToEnd() }); form.ShowDialog(); }};
        FormClosing += (s,e) => { if(busy) e.Cancel=true; };
        install.Click += async (s,e) => {
            if(!accept.Checked) { MessageBox.Show("Önce lisans ve kullanım koşullarını okuyup kabul edin."); return; }
            if(Directory.Exists(root) && File.Exists(Path.Combine(root,"current.json"))) { MessageBox.Show("Uygulama zaten kurulu. OtoTrend'i açarak otomatik güncellemeyi kullanın."); return; }
            busy=true; install.Enabled=false; accept.Enabled=false;
            string temp=Path.Combine(Path.GetTempPath(),"ototrend-setup-"+Guid.NewGuid().ToString("N"));
            try {
                await Task.Run(() => {
                    Directory.CreateDirectory(temp);
                    using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("bootstrap.zip"))
                    using(var archive=new ZipArchive(stream)) { archive.ExtractToDirectory(temp); }
                    string args="\""+Path.Combine(temp,"desktop","install.py")+"\" --source \""+AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\')+"\" --root \""+root+"\"";
                    using(var process=new Process()) {
                        process.StartInfo=new ProcessStartInfo(Path.Combine(temp,"runtime","python.exe"),args) { UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8 };
                        process.OutputDataReceived += (a,b) => { if(b.Data!=null) BeginInvoke(new Action(() => output.AppendText(b.Data+"\r\n"))); };
                        process.ErrorDataReceived += (a,b) => { if(b.Data!=null) BeginInvoke(new Action(() => output.AppendText(b.Data+"\r\n"))); };
                        process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit();
                        if(process.ExitCode!=0) throw new Exception("Kurulum tamamlanamadı; açıklamayı kontrol edin.");
                    }
                });
                MessageBox.Show("Kurulum tamamlandı. Başlat menüsünden OtoTrend AI'ı açabilirsiniz.");
            } catch(Exception error) { MessageBox.Show(error.Message,"Kurulum hatası"); }
            finally { busy=false; install.Enabled=true; accept.Enabled=true; try { Directory.Delete(temp,true); } catch {} }
        };
    }
    [STAThread] static void Main() { if(!Environment.Is64BitOperatingSystem) { MessageBox.Show("Windows 10/11 64-bit gereklidir."); return; } Application.EnableVisualStyles(); Application.Run(new Setup()); }
}
