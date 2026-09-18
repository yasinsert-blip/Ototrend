using System;
using System.IO;
using System.Text;
using System.Reflection;
using System.Security.Cryptography;
using System.Diagnostics;
using System.Web.Script.Serialization;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Windows.Forms;
class Launcher {
    [STAThread] static void Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            if(args.Length==1 && args[0]=="--stop") {
                Directory.CreateDirectory(Path.Combine(root,"data"));
                File.WriteAllText(Path.Combine(root,"data","stop.request"),"stop");
                MessageBox.Show("Kapatma istendi. Devam eden işler tamamlandıktan sonra OtoTrend kapanacak.","OtoTrend AI");
                return;
            }
            var json = new JavaScriptSerializer();
            var pointer = json.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(root,"current.json")));
            byte[] raw = Convert.FromBase64String(pointer["manifest"]);
            using (var rsa = new RSACryptoServiceProvider()) {
                rsa.PersistKeyInCsp = false;
                using(var reader = new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("public-key.xml"))) rsa.FromXmlString(reader.ReadToEnd());
                if (!rsa.VerifyData(raw, CryptoConfig.MapNameToOID("SHA256"), Convert.FromBase64String(pointer["signature"]))) throw new Exception("Sürüm imzası geçersiz.");
            }
            dynamic data = json.DeserializeObject(Encoding.UTF8.GetString(raw));
            string hash = data["components"]["application"]["sha256"];
            if (!Regex.IsMatch(hash, "^[0-9a-f]{64}$")) throw new Exception("Geçersiz sürüm.");
            string release = Path.Combine(root,"versions","application-" + hash);
            Process.Start(new ProcessStartInfo(Path.Combine(release,"runtime","pythonw.exe"), "\"" + Path.Combine(release,"desktop","launcher.py") + "\" \"" + root.TrimEnd('\\') + "\"") { UseShellExecute=false, CreateNoWindow=true, WorkingDirectory=root });
        } catch(Exception e) { MessageBox.Show(e.Message,"OtoTrend AI"); }
    }
}
