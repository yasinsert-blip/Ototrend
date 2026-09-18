using System;
using System.IO;
using System.Text;
using System.Security.Cryptography;

// The private release key is encrypted for the current Windows account.
class KeyTool {
    static int Main(string[] args) {
        try {
            if (args.Length < 3) throw new Exception("init key.dpapi public.xml | sign key.dpapi input output");
            using (var rsa = new RSACryptoServiceProvider(3072)) {
                rsa.PersistKeyInCsp = false;
                if (args[0] == "init") {
                    if (File.Exists(args[1]) || File.Exists(args[2])) throw new Exception("Existing keys will not be overwritten.");
                    File.WriteAllBytes(args[1], ProtectedData.Protect(Encoding.UTF8.GetBytes(rsa.ToXmlString(true)), null, DataProtectionScope.CurrentUser));
                    File.WriteAllText(args[2], rsa.ToXmlString(false));
                } else if (args[0] == "sign" && args.Length == 4) {
                    rsa.FromXmlString(Encoding.UTF8.GetString(ProtectedData.Unprotect(File.ReadAllBytes(args[1]), null, DataProtectionScope.CurrentUser)));
                    File.WriteAllBytes(args[3], rsa.SignData(File.ReadAllBytes(args[2]), CryptoConfig.MapNameToOID("SHA256")));
                } else throw new Exception("Invalid arguments.");
            }
            return 0;
        } catch (Exception e) { Console.Error.WriteLine(e.GetType().Name + ": " + e.Message); return 1; }
    }
}
