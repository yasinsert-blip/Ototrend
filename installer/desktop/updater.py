"""Download signed stable releases; activate only before the server is started."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.request

from bundle import REPOSITORY, read_manifest, fetch, current, component_path, install_components, activate, sha256


def stage_update(root, key):
    installed = current(root, key)
    latest = json.loads(fetch(f'https://api.github.com/repos/{REPOSITORY}/releases/latest', 512 * 1024))
    if latest.get('draft') or latest.get('prerelease'):
        return
    tag = latest.get('tag_name', '')
    from bundle import VERSION
    if not tag.startswith('v') or not VERSION.fullmatch(tag[1:]):
        return
    if tuple(map(int, tag[1:].split('.'))) <= tuple(map(int, installed['version'].split('.'))):
        return
    base = f'https://github.com/{REPOSITORY}/releases/download/{tag}/'
    raw, signature = fetch(base + 'release.json', 128 * 1024), fetch(base + 'release.sig', 1024)
    candidate = read_manifest(raw, signature, key)
    if 'v' + candidate['version'] != tag:
        raise ValueError('Sürüm etiketi eşleşmedi')
    folder = Path(root) / 'updates' / tag
    folder.mkdir(parents=True, exist_ok=True)
    for kind, component in candidate['components'].items():
        if (component_path(root, kind, component) / '.complete').exists():
            continue
        for part in component['parts']:
            target = folder / part['name']
            if target.exists() and target.stat().st_size == part['bytes'] and sha256(target) == part['sha256']:
                continue
            import shutil
            if shutil.disk_usage(folder).free < part['bytes'] + 512 * 1024**2:
                raise ValueError('Güncelleme için disk alanı yetersiz')
            temporary = target.with_suffix(target.suffix + '.partial')
            request = urllib.request.Request(base + part['name'], headers={'User-Agent': 'OtoTrend-Desktop/2.2'})
            started, total = time.monotonic(), 0
            with urllib.request.urlopen(request, timeout=30) as response, temporary.open('wb') as out:
                if not response.url.startswith('https://'):
                    raise ValueError('Güvensiz yönlendirme')
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > part['bytes'] or time.monotonic() - started > 3600:
                        raise ValueError('Güncelleme indirme sınırı aşıldı')
                    out.write(block)
            if total != part['bytes'] or sha256(temporary) != part['sha256']:
                raise ValueError('İndirilen güncelleme bozuk')
            os.replace(temporary, target)
    (folder / 'release.json').write_bytes(raw)
    (folder / 'release.sig').write_bytes(signature)
    # Written last: no partial download can become a pending update.
    pending = Path(root) / 'pending.new'
    pending.write_text(tag, encoding='ascii')
    os.replace(pending, Path(root) / 'pending.txt')


def apply_pending(root, key):
    root = Path(root)
    pending = root / 'pending.txt'
    if not pending.exists():
        return False
    from bundle import VERSION
    tag = pending.read_text(encoding='ascii')
    if not tag.startswith('v') or not VERSION.fullmatch(tag[1:]):
        raise ValueError('Geçersiz bekleyen sürüm')
    source = root / 'updates' / tag
    raw, signature = (source / 'release.json').read_bytes(), (source / 'release.sig').read_bytes()
    manifest = read_manifest(raw, signature, key)
    old = current(root, key)
    if tuple(map(int, manifest['version'].split('.'))) <= tuple(map(int, old['version'].split('.'))):
        pending.unlink()
        return False
    install_components(root, source, manifest)
    application = component_path(root, 'application', manifest['components']['application'])
    dbpath = root / 'data' / 'news.db'
    backup = None
    if dbpath.exists():
        backups = root / 'data' / 'backups'
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / ('before-' + tag + '-' + str(time.time_ns()) + '.db')
        with closing(sqlite3.connect(dbpath)) as src, closing(sqlite3.connect(backup)) as dst:
            src.backup(dst)
    # No server is running: caller owns installation lock for the entire operation.
    logs = root / 'data' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / 'update-probe.log').open('a', encoding='utf-8') as log:
        try:
            result = subprocess.run([str(application / 'runtime' / 'python.exe'), str(application / 'desktop' / 'runner.py'), str(root), '--probe'],
                                    stdout=log, stderr=log, timeout=120, creationflags=0x08000000 if os.name == 'nt' else 0)
            if result.returncode:
                raise RuntimeError('Yeni sürüm başlangıç kontrolünü geçemedi')
        except Exception:
            if backup:
                with closing(sqlite3.connect(backup)) as src, closing(sqlite3.connect(dbpath)) as dst:
                    src.backup(dst)
            raise
    activate(root, raw, signature)
    pending.unlink()
    return True
