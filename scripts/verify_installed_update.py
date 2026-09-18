"""Local signed update integration test on a synthetic installed fixture only."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer/desktop'))
from bundle import current
from updater import apply_pending


def main():
    root = Path(sys.argv[1]).resolve()
    if not root.is_relative_to(ROOT / 'build') or not root.name.startswith('install-smoke-'):
        raise ValueError('Synthetic install-smoke fixture required')
    key = (ROOT / 'installer/desktop/public-key.xml').read_bytes()
    manifest = current(root, key)
    candidate = json.loads(json.dumps(manifest))
    candidate['version'] = '999.0.0'
    folder = root / 'updates/v999.0.0'
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'release.json').write_text(json.dumps(candidate), encoding='utf-8')
    subprocess.run([str(ROOT / 'installer/vendor/KeyTool.exe'), 'sign', str(ROOT / 'installer/private/release-key.dpapi'), str(folder / 'release.json'), str(folder / 'release.sig')], check=True)
    # Known fixture record demonstrates successful migration does not erase data.
    db = root / 'data/news.db'
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute('CREATE TABLE IF NOT EXISTS installer_sentinel (value TEXT)')
        connection.execute("INSERT INTO installer_sentinel VALUES ('preserve-me')")
    before_config = (root / 'data/.env').read_bytes()
    (root / 'pending.txt').write_text('v999.0.0', encoding='ascii')
    assert apply_pending(root, key)
    assert current(root, key)['version'] == '999.0.0'
    assert (root / 'data/.env').read_bytes() == before_config
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute('SELECT value FROM installer_sentinel').fetchone()[0] == 'preserve-me'
    assert list((root / 'data/backups').glob('before-v999.0.0-*.db'))
    assert not (root / 'pending.txt').exists()
    print('SIGNED_UPDATE_AND_DATA_PRESERVATION_OK')


if __name__ == '__main__':
    main()
