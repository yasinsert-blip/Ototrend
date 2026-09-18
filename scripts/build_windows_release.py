"""Build a signed offline Windows release from audited local dependencies.

No credentials, databases, virtual environments or working logs are packaged.
Outputs are never published automatically by this script.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'installer' / 'desktop'))
from installer_inventory import inventory
from bundle import REPOSITORY, VERSION, sha256

CSC = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
VENDOR = ROOT / 'installer' / 'vendor'


def download(url, path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print('Downloading: ' + path.name, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'OtoTrend-release-builder/2.2'})
    with urllib.request.urlopen(request, timeout=60) as response, path.open('xb') as out:
        shutil.copyfileobj(response, out, 1024 * 1024)


def add_tree(files, root, prefix):
    for path in root.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and not path.is_symlink():
            files[prefix + '/' + path.relative_to(root).as_posix()] = path


def archive_component(kind, files, output):
    archive = output / (kind + '.zip')
    total = 0
    print('Packaging: ' + kind, flush=True)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED if kind == 'models' else zipfile.ZIP_DEFLATED, compresslevel=1) as zipout:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipout.compression
            info.external_attr = 0o100644 << 16
            with path.open('rb') as src, zipout.open(info, 'w', force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            total += path.stat().st_size
    digest = sha256(archive)
    parts = []
    # 1 GiB is comfortably below GitHub's per-asset cap.
    if archive.stat().st_size > 1024**3:
        with archive.open('rb') as src:
            index = 1
            while True:
                first = src.read(1024 * 1024)
                if not first:
                    break
                part = output / (archive.name + '.part' + str(index).zfill(3))
                with part.open('xb') as dst:
                    dst.write(first)
                    remaining = 1024**3 - len(first)
                    while remaining:
                        block = src.read(min(1024 * 1024, remaining))
                        if not block:
                            break
                        dst.write(block)
                        remaining -= len(block)
                parts.append({'name': part.name, 'bytes': part.stat().st_size, 'sha256': sha256(part)})
                index += 1
        # This is the generated build archive, never a user's source/data file.
        archive.unlink()
    else:
        parts.append({'name': archive.name, 'bytes': archive.stat().st_size, 'sha256': digest})
    return {'sha256': digest, 'unpacked_bytes': total, 'parts': parts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--output-name', help='New folder name under dist; never overwrites an existing build')
    parser.add_argument('--reuse-components-from', type=Path)
    parser.add_argument('--reuse-source-repository', default=REPOSITORY,
                        help='Expected repository of a locally cached, signed tools/model bundle; never affects update trust')
    parser.add_argument('--ollama', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Programs' / 'Ollama')
    parser.add_argument('--models', type=Path, default=Path.home() / '.ollama' / 'models')
    parser.add_argument('--browsers', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')
    args = parser.parse_args()
    if not VERSION.fullmatch(args.version):
        raise ValueError('Expected numeric x.y.z version')
    output_name = args.output_name or ('v' + args.version)
    import re
    if not re.fullmatch('[a-zA-Z0-9._-]+', output_name) or output_name in ('.', '..'):
        raise ValueError('Invalid output folder name')
    output = ROOT / 'dist' / output_name
    output.mkdir(parents=True, exist_ok=False)
    runtime = VENDOR / 'python313'
    public = ROOT / 'installer' / 'desktop' / 'public-key.xml'
    private = ROOT / 'installer' / 'private' / 'release-key.dpapi'
    if not public.exists() or not private.exists():
        raise ValueError('Release signing key not prepared')
    desktop = ROOT / 'installer' / 'desktop'
    subprocess.run([str(CSC), '/nologo', '/target:winexe', '/out:' + str(VENDOR / 'OtoTrend.exe'),
                    '/reference:System.Windows.Forms.dll', '/reference:System.Web.Extensions.dll', '/reference:Microsoft.CSharp.dll',
                    '/resource:' + str(public) + ',public-key.xml', str(ROOT / 'installer' / 'Launcher.cs')], check=True)
    app_files = {'application/' + item['path']: ROOT / item['path'] for item in inventory()}
    add_tree(app_files, runtime, 'runtime')
    add_tree(app_files, desktop, 'desktop')
    app_files['desktop/OtoTrend.exe'] = VENDOR / 'OtoTrend.exe'
    licenses = VENDOR / 'licenses'
    licenses.mkdir(exist_ok=True)
    from bs4 import BeautifulSoup
    for name, url in [('GEMMA-TERMS', 'https://ai.google.dev/gemma/terms'), ('GEMMA-PROHIBITED-USE', 'https://ai.google.dev/gemma/prohibited_use_policy')]:
        html = licenses / (name + '.html')
        download(url, html)
        soup = BeautifulSoup(html.read_text(encoding='utf-8'), 'html.parser')
        article = soup.find('article') or soup
        (licenses / (name + '.txt')).write_text(article.get_text('\n', strip=True), encoding='utf-8')
    download('https://raw.githubusercontent.com/ollama/ollama/v0.34.0/LICENSE', licenses / 'OLLAMA-LICENSE.txt')
    notice = licenses / 'NOTICE.txt'
    notice.write_text('Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms\nBundled Gemma 3 usage is subject to the included GEMMA-TERMS and GEMMA-PROHIBITED-USE documents.\nCPU-only Ollama runtime. GPU acceleration is not included.\nPython package licenses are included in runtime/Lib/site-packages/*.dist-info.\n', encoding='utf-8')
    add_tree(app_files, licenses, 'licenses')
    terms = VENDOR / 'setup-terms.txt'
    terms.write_text((licenses / 'GEMMA-TERMS.txt').read_text(encoding='utf-8') + '\n\n' + (licenses / 'GEMMA-PROHIBITED-USE.txt').read_text(encoding='utf-8'), encoding='utf-8')

    # Vendored CSS/JS keep the editor functional without CDN access.
    assets = {
        'bootstrap-5.3.3.css': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
        'bootstrap-5.3.3.js': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
        'bootstrap-5.3.7.css': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css',
        'bootstrap-5.3.7.js': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js',
        'chart.js': 'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js',
    }
    for version in ('1.11.3', '1.13.1'):
        assets['icons-' + version + '/bootstrap-icons.css'] = f'https://cdn.jsdelivr.net/npm/bootstrap-icons@{version}/font/bootstrap-icons.css'
        for ext in ('woff', 'woff2'):
            assets['icons-' + version + '/fonts/bootstrap-icons.' + ext] = f'https://cdn.jsdelivr.net/npm/bootstrap-icons@{version}/font/fonts/bootstrap-icons.{ext}'
    for name, url in assets.items():
        path = VENDOR / 'web' / name
        download(url, path)
        app_files['application/app/static/vendor/' + name] = path
    for label, url in [('BOOTSTRAP-LICENSE.txt','https://raw.githubusercontent.com/twbs/bootstrap/v5.3.3/LICENSE'), ('BOOTSTRAP-ICONS-LICENSE.txt','https://raw.githubusercontent.com/twbs/icons/v1.13.1/LICENSE'), ('CHARTJS-LICENSE.txt','https://raw.githubusercontent.com/chartjs/Chart.js/v4.4.7/LICENSE.md')]:
        download(url, licenses / label)
        app_files['licenses/' + label] = licenses / label
    import re
    for name, original in list(app_files.items()):
        if name.startswith('application/app/templates/') and original.suffix == '.html':
            text = original.read_text(encoding='utf-8')
            for asset, url in assets.items():
                text = text.replace(url, '/static/vendor/' + asset)
            text = re.sub(r'<link\b[^>]*https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', text, flags=re.S)
            replacement = VENDOR / 'rendered-templates' / Path(name).relative_to('application/app/templates')
            replacement.parent.mkdir(parents=True, exist_ok=True)
            replacement.write_text(text, encoding='utf-8')
            app_files[name] = replacement

    tool_files = {'ollama/ollama.exe': args.ollama / 'ollama.exe'}
    for path in (args.ollama / 'lib' / 'ollama').iterdir():
        if path.is_file():
            tool_files['ollama/lib/ollama/' + path.name] = path
    browser_config = json.loads((runtime / 'Lib/site-packages/playwright/driver/package/browsers.json').read_text())
    for item in browser_config['browsers']:
        if item['name'] not in ('chromium', 'chromium-headless-shell', 'ffmpeg', 'winldd'):
            continue
        revision = item.get('revisionOverrides', {}).get('win64', item['revision'])
        folder = item['name'].replace('-', '_') + '-' + revision
        location = args.browsers / folder
        if not location.exists():
            raise ValueError('Missing browser runtime: ' + folder)
        add_tree(tool_files, location, 'browsers/' + folder)
    model_manifest = args.models / 'manifests/registry.ollama.ai/library/gemma3/4b'
    model_files = {'models/manifests/registry.ollama.ai/library/gemma3/4b': model_manifest}
    model = json.loads(model_manifest.read_text())
    for layer in [model['config'], *model['layers']]:
        filename = layer['digest'].replace(':', '-')
        file = args.models / 'blobs' / filename
        if file.stat().st_size != layer['size'] or sha256(file) != layer['digest'].split(':')[1]:
            raise ValueError('Model blob validation failed')
        model_files['models/blobs/' + filename] = file
    manifest = {'schema': 1, 'repository': REPOSITORY, 'version': args.version, 'components': {}}
    reuse = None
    if args.reuse_components_from:
        from bundle import read_manifest
        reuse = read_manifest((args.reuse_components_from / 'release.json').read_bytes(), (args.reuse_components_from / 'release.sig').read_bytes(), public.read_bytes(), expected_repository=args.reuse_source_repository)
    for name, files in [('application', app_files), ('tools', tool_files), ('models', model_files)]:
        if reuse and name in ('tools', 'models'):
            component = reuse['components'][name]
            for part in component['parts']:
                original = args.reuse_components_from / part['name']
                if original.stat().st_size != part['bytes'] or sha256(original) != part['sha256']:
                    raise ValueError('Cached component is corrupt')
                os.link(original, output / part['name'])
            manifest['components'][name] = component
        else:
            manifest['components'][name] = archive_component(name, files, output)
    (output / 'release.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    subprocess.run([str(VENDOR / 'KeyTool.exe'), 'sign', str(private), str(output / 'release.json'), str(output / 'release.sig')], check=True)
    # The bootstrap is stdlib-only, no host Python installation is required.
    bootstrap_files = {}
    for path in runtime.iterdir():
        if path.is_file():
            bootstrap_files['runtime/' + path.name] = path
    for name in ('install.py', 'bundle.py', 'public-key.xml'):
        bootstrap_files['desktop/' + name] = desktop / name
    bootstrap = VENDOR / 'bootstrap.zip'
    with zipfile.ZipFile(bootstrap, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        for name, path in bootstrap_files.items():
            out.write(path, name)
    subprocess.run([str(CSC), '/nologo', '/target:winexe', '/out:' + str(output / 'Setup.exe'), '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
                    '/resource:' + str(bootstrap) + ',bootstrap.zip', '/resource:' + str(terms) + ',terms.txt', str(ROOT / 'installer' / 'Setup.cs')], check=True)
    (output / 'KURULUM.txt').write_text('Tüm dosyaları aynı klasöre indirin ve Setup.exe dosyasını çalıştırın.\nWindows 10 22H2 / Windows 11 x64, CPU çalışması. En az 15 GB boş alan önerilir.\nKurulum ve model çevrimdışı kullanılabilir; haber taraması ve Telegram için internet gerekir.\nBaşlat menüsü: OtoTrend AI; kapatmak için OtoTrend AI - Kapat.\nTarayıcıyı kapatmak haber taramasını durdurmaz.\nGüncellemeler arka planda iner ve sonraki uygulama açılışında otomatik uygulanır.\nSmartScreen uyarısı görülebilir; Windows yayıncı sertifikası yoktur.\n', encoding='utf-8')
    print('Release built: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
