"""Publish a verified offline build to a draft GitHub Release first.

Uses the configured Git credential helper; never prints its credential.
The separate --publish flag is required to expose an already uploaded draft.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer/desktop'))
from bundle import REPOSITORY, read_manifest, sha256


def credentials():
    result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n', capture_output=True, text=True, check=True, timeout=30)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if not values.get('password'):
        raise RuntimeError('GitHub credential unavailable')
    return values['password']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    import re
    if not re.fullmatch('[a-f0-9]{40}', args.commit):
        raise ValueError('Exact source commit required')
    folder = args.directory.resolve()
    raw, signature = (folder / 'release.json').read_bytes(), (folder / 'release.sig').read_bytes()
    manifest = read_manifest(raw, signature, (ROOT / 'installer/desktop/public-key.xml').read_bytes())
    files = ['release.json', 'release.sig', 'Setup.exe', 'KURULUM.txt']
    for component in manifest['components'].values():
        for part in component['parts']:
            path = folder / part['name']
            if path.stat().st_size != part['bytes'] or sha256(path) != part['sha256']:
                raise ValueError('Invalid release asset: ' + part['name'])
            files.append(part['name'])
    session = requests.Session()
    session.headers.update(Authorization='Bearer ' + credentials(), Accept='application/vnd.github+json', **{'X-GitHub-Api-Version': '2022-11-28'})
    api = f'https://api.github.com/repos/{REPOSITORY}'
    def request(method, url, **kwargs):
        response = session.request(method, url, timeout=(20, 1800), **kwargs)
        if not response.ok:
            raise RuntimeError('GitHub request failed: HTTP ' + str(response.status_code))
        return response.json() if response.content else None
    # Explicit repository and source commit, never a guessed moving branch.
    request('GET', api + '/commits/' + args.commit)
    tag = 'v' + manifest['version']
    releases = request('GET', api + '/releases?per_page=100')
    release = next((item for item in releases if item['tag_name'] == tag), None)
    if release is None:
        if args.publish:
            raise ValueError('Upload a draft before publishing')
        notes = 'Windows 10 22H2 / Windows 11 x64 için çevrimdışı kurulum.\n\nTüm varlıkları aynı klasöre indirin ve Setup.exe dosyasını çalıştırın. Python, Chromium, CPU Ollama ve Gemma 3 4B model dosyaları dahildir. Haber taraması, Telegram ve güncelleme indirmeleri internet gerektirir.\n\nKişisel ayarlar ve haber veritabanı dahil değildir; ilk açılışta kendi yönetici ve Telegram bilgilerinizi girin. Windows yayıncı sertifikası bulunmadığından SmartScreen uyarısı görülebilir.\n\nGüncellemeler imza kontrolünden sonra arka planda indirilir; sonraki uygulama açılışında veri yedeği alınarak uygulanır.\n\nBaşlat menüsündeki OtoTrend AI - Kapat ile arka plan uygulamasını kapatabilirsiniz. Tarayıcıyı kapatmak taramayı durdurmaz.\n\nTest: yalıtılmış Windows klasöründe kurulum, dış ağ istekleri kapalı tarayıcı testi ve model kayıt kontrolü. Ayrı fiziksel bilgisayarda test edilmedi.'
        release = request('POST', api + '/releases', json={'tag_name': tag, 'target_commitish': args.commit, 'name': 'OtoTrend AI ' + tag + ' — Windows çevrimdışı kurulum', 'body': notes, 'draft': True, 'prerelease': False})
    if not release['draft']:
        raise ValueError('Existing public release is immutable to this tool')
    if release['target_commitish'] != args.commit:
        raise ValueError('Draft source commit mismatch')
    assets = request('GET', api + '/releases/' + str(release['id']) + '/assets?per_page=100')
    for name in files:
        path = folder / name
        digest = 'sha256:' + sha256(path)
        existing = next((item for item in assets if item['name'] == name), None)
        if existing:
            if existing.get('digest') != digest or existing['size'] != path.stat().st_size or existing['state'] != 'uploaded':
                raise ValueError('Existing draft asset mismatch: ' + name)
            print('Verified remote: ' + name, flush=True)
            continue
        if args.publish:
            raise ValueError('Missing draft asset: ' + name)
        print('Uploading: ' + name, flush=True)
        url = f'https://uploads.github.com/repos/{REPOSITORY}/releases/{release["id"]}/assets?name=' + quote(name)
        with path.open('rb') as stream:
            uploaded = request('POST', url, data=stream, headers={'Content-Type': 'application/octet-stream', 'Content-Length': str(path.stat().st_size)})
        if uploaded.get('digest') != digest:
            raise ValueError('Remote checksum mismatch: ' + name)
    if args.publish:
        release = request('PATCH', api + '/releases/' + str(release['id']), json={'draft': False, 'make_latest': 'true'})
        print('Published: ' + release['html_url'], flush=True)
    else:
        print('Draft upload complete; not public yet.', flush=True)


if __name__ == '__main__':
    main()
