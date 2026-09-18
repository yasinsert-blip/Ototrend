"""Signed, bounded offline bundle handling; no application imports or secrets."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

REPOSITORY = 'yasinsert-blip/Ototrend'
VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
NAME = re.compile(r'^[a-z0-9][a-z0-9._-]{0,99}$')
MAX_PART = 1900 * 1024 * 1024
MAX_EXTRACT = 20 * 1024**3


def verify_signature(data, signature, key):
    xml = ET.fromstring(key)
    n = int.from_bytes(base64.b64decode(xml.findtext('Modulus')), 'big')
    e = int.from_bytes(base64.b64decode(xml.findtext('Exponent')), 'big')
    length = (n.bit_length() + 7) // 8
    if len(signature) != length or int.from_bytes(signature, 'big') >= n:
        raise ValueError('Geçersiz güncelleme imzası')
    tail = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(data).digest()
    expected = b'\x00\x01' + b'\xff' * (length - len(tail) - 3) + b'\x00' + tail
    actual = pow(int.from_bytes(signature, 'big'), e, n).to_bytes(length, 'big')
    if not hmac.compare_digest(expected, actual):
        raise ValueError('Güncelleme imzası doğrulanamadı')


def read_manifest(raw, signature, public_key, expected_repository=REPOSITORY):
    if len(raw) > 128 * 1024:
        raise ValueError('Manifest çok büyük')
    verify_signature(raw, signature, public_key)
    data = json.loads(raw)
    if data.get('repository') != expected_repository or data.get('schema') != 1 or not VERSION.fullmatch(data.get('version', '')):
        raise ValueError('Geçersiz sürüm manifesti')
    if set(data.get('components', {})) != {'application', 'tools', 'models'}:
        raise ValueError('Eksik paket bileşeni')
    names = set()
    for component in data['components'].values():
        if not re.fullmatch('[0-9a-f]{64}', component.get('sha256', '')):
            raise ValueError('Geçersiz özet')
        if not 0 < component.get('unpacked_bytes', 0) <= MAX_EXTRACT:
            raise ValueError('Paket boyutu sınır dışında')
        if not 1 <= len(component.get('parts', [])) <= 32:
            raise ValueError('Geçersiz parça sayısı')
        for part in component['parts']:
            if not NAME.fullmatch(part.get('name', '')) or part['name'] in names:
                raise ValueError('Geçersiz veya yinelenen parça adı')
            names.add(part['name'])
            if not 0 < part.get('bytes', 0) <= MAX_PART or not re.fullmatch('[0-9a-f]{64}', part.get('sha256', '')):
                raise ValueError('Geçersiz parça bilgisi')
    return data


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or name.startswith('/'):
        raise ValueError('Güvensiz arşiv yolu')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(1, 10)), *('LPT' + str(i) for i in range(1, 10))}
    for piece in path.parts:
        if piece in ('.', '..') or piece.endswith((' ', '.')) or piece.split('.')[0].upper() in reserved:
            raise ValueError('Güvensiz arşiv yolu')
    return path


def extract(archive, destination, limit):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > 100000 or sum(item.file_size for item in entries) > limit:
            raise ValueError('Arşiv açılma sınırı aşıldı')
        seen = set()
        for item in entries:
            relative = safe_member(item.filename)
            key = str(relative).casefold()
            if key in seen or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Yinelenen dosya veya bağlantı')
            seen.add(key)
            target = destination.joinpath(*relative.parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)


def component_path(root, kind, component):
    return Path(root) / ('versions' if kind == 'application' else 'shared') / (kind + '-' + component['sha256'])


def install_components(root, source, manifest, progress=print):
    root, source = Path(root), Path(source)
    root.mkdir(parents=True, exist_ok=True)
    for kind, component in manifest['components'].items():
        target = component_path(root, kind, component)
        if (target / '.complete').is_file():
            progress(kind + ': mevcut bileşen korunuyor')
            continue
        if target.exists():
            raise ValueError('Yarım kalmış hedef bulundu; otomatik üzerine yazılmadı')
        required = component['unpacked_bytes'] + sum(p['bytes'] for p in component['parts'])
        if shutil.disk_usage(root).free < required + 512 * 1024**2:
            raise ValueError('Kurulum için yeterli disk alanı yok')
        progress(kind + ': doğrulanıyor ve açılıyor')
        with tempfile.TemporaryDirectory(prefix='ototrend-stage-', dir=root) as stage:
            archive = Path(stage) / 'component.zip'
            with archive.open('xb') as output:
                for part in component['parts']:
                    file = source / part['name']
                    if file.is_symlink() or file.stat().st_size != part['bytes'] or sha256(file) != part['sha256']:
                        raise ValueError('Paket parçası bozuk: ' + part['name'])
                    with file.open('rb') as incoming:
                        shutil.copyfileobj(incoming, output, 1024 * 1024)
            if sha256(archive) != component['sha256']:
                raise ValueError('Paket özeti eşleşmedi')
            unpacked = Path(stage) / 'unpacked'
            extract(archive, unpacked, component['unpacked_bytes'])
            (unpacked / '.complete').write_text('1', encoding='ascii')
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(unpacked, target)


def activate(root, raw, signature):
    # Pointer contains the signed bytes, avoiding a two-file activation window.
    root = Path(root)
    pointer = json.dumps({'manifest': base64.b64encode(raw).decode(), 'signature': base64.b64encode(signature).decode()})
    temporary = root / 'current.new'
    temporary.write_text(pointer, encoding='utf-8')
    os.replace(temporary, root / 'current.json')


def current(root, key):
    pointer = json.loads((Path(root) / 'current.json').read_text(encoding='utf-8'))
    return read_manifest(base64.b64decode(pointer['manifest']), base64.b64decode(pointer['signature']), key)


def fetch(url, limit):
    if not url.startswith('https://'):
        raise ValueError('HTTPS gerekli')
    request = urllib.request.Request(url, headers={'User-Agent': 'OtoTrend-Desktop/2.2', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Güvensiz yönlendirme')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('İndirme sınırı aşıldı')
    return data
