import argparse
from pathlib import Path
import shutil
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

from bundle import read_manifest, install_components, activate, component_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--no-shortcuts', action='store_true')
    args = parser.parse_args()
    key = Path(__file__).with_name('public-key.xml').read_bytes()
    raw = (args.source / 'release.json').read_bytes()
    signature = (args.source / 'release.sig').read_bytes()
    manifest = read_manifest(raw, signature, key)
    root = args.root.resolve()
    if (root / 'current.json').exists():
        raise RuntimeError('Bu dizinde kurulum mevcut. Mevcut uygulamanın güncelleyicisini kullanın.')
    install_components(root, args.source, manifest, lambda message: print(message, flush=True))
    application = component_path(root, 'application', manifest['components']['application'])
    shutil.copy2(application / 'desktop' / 'OtoTrend.exe', root / 'OtoTrend.exe')
    activate(root, raw, signature)
    if not args.no_shortcuts:
        import os
        env = dict(os.environ, OTOTREND_INSTALL_ROOT=str(root))
        script = "$rootPath=$env:OTOTREND_INSTALL_ROOT; $shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Programs'),'OtoTrend AI.lnk')); $link.TargetPath=[IO.Path]::Combine($rootPath,'OtoTrend.exe'); $link.WorkingDirectory=$rootPath; $link.Save(); $stop=$shell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Programs'),'OtoTrend AI - Kapat.lnk')); $stop.TargetPath=$link.TargetPath; $stop.Arguments='--stop'; $stop.Save()"
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], env=env, check=True, creationflags=0x08000000)
    print('Kurulum tamamlandı. OtoTrend.exe ile açabilirsiniz.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Kurulum tamamlanamadı: ' + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
