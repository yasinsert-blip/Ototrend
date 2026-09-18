import base64
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installer' / 'desktop'))
import bundle
import updater


class DesktopBundleTests(unittest.TestCase):
    def test_reject_windows_and_zip_slip_paths(self):
        for name in ('../secret', '/absolute', 'C:/file', 'a\\b', 'a/../b', 'CON.txt', 'a/file.', 'a/file ', 'a:stream'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.safe_member(name)

    def test_accept_normal_member(self):
        self.assertEqual(str(bundle.safe_member('app/templates/index.html')), 'app/templates/index.html')

    def archive(self, directory, entries):
        archive = directory / 'test.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            for name, data in entries:
                out.writestr(name, data)
        return archive

    def test_case_collision_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.archive(root, [('file.txt', 'a'), ('FILE.txt', 'b')])
            with self.assertRaises(ValueError):
                bundle.extract(archive, root / 'out', 100)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            link = zipfile.ZipInfo('shortcut')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive = self.archive(root, [(link, '../private')])
            with self.assertRaises(ValueError):
                bundle.extract(archive, root / 'out', 100)

    def test_extraction_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.archive(root, [('file', 'abc')])
            with self.assertRaises(ValueError):
                bundle.extract(archive, root / 'out', 2)

    def test_verified_component_preserves_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            archive = self.archive(source, [('application/main.py', 'print(1)')])
            digest = bundle.sha256(archive)
            component = dict(sha256=digest, unpacked_bytes=8, parts=[dict(name='test.zip', bytes=archive.stat().st_size, sha256=digest)])
            install = root / 'install'
            (install / 'data').mkdir(parents=True)
            (install / 'data' / '.env').write_text('private')
            bundle.install_components(install, source, {'components': {'application': component}}, lambda _: None)
            self.assertEqual((install / 'data' / '.env').read_text(), 'private')
            self.assertEqual((bundle.component_path(install, 'application', component) / 'application/main.py').read_text(), 'print(1)')

    def test_bad_component_hash_not_activated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.archive(root, [('file', 'abc')])
            component = dict(sha256='0'*64, unpacked_bytes=3, parts=[dict(name='test.zip', bytes=archive.stat().st_size, sha256='0'*64)])
            with self.assertRaises(ValueError):
                bundle.install_components(root / 'install', root, {'components': {'application': component}}, lambda _: None)
            self.assertFalse((root / 'install' / 'current.json').exists())

    def test_invalid_signature_rejected(self):
        public = Path(__file__).resolve().parents[1] / 'installer/desktop/public-key.xml'
        with self.assertRaises(ValueError):
            bundle.verify_signature(b'anything', b'bad', public.read_bytes())

    def test_updater_rejects_previous_repository(self):
        raw = json.dumps({'repository': 'ototrendtr-cmyk/OtoTrend-AI-Newsroom', 'schema': 1, 'version': '2.3.0'}).encode()
        with patch.object(bundle, 'verify_signature'), self.assertRaises(ValueError):
            bundle.read_manifest(raw, b'signature', b'key')
        self.assertEqual(bundle.REPOSITORY, 'yasinsert-blip/Ototrend')

    def test_onboarding_creates_private_settings_without_default_password(self):
        import onboarding
        import queue
        import threading
        import urllib.parse
        import urllib.request
        from dotenv import dotenv_values
        with tempfile.TemporaryDirectory() as temp:
            urls = queue.Queue()
            errors = []
            def run():
                try:
                    onboarding.configure(Path(temp))
                except Exception as error:
                    errors.append(error)
            with patch.object(onboarding.webbrowser, 'open', side_effect=lambda url: urls.put(url)):
                worker = threading.Thread(target=run, daemon=True)
                worker.start()
                url = urls.get(timeout=5)
                with urllib.request.urlopen(url, timeout=5) as response:
                    self.assertIn('OtoTrend', response.read().decode())
                password = "correct horse ' \\ battery"
                body = urllib.parse.urlencode({'username': 'new-owner', 'password': password}).encode()
                with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=5) as response:
                    self.assertEqual(response.status, 200)
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            settings = dotenv_values(Path(temp) / 'data/.env')
            self.assertEqual(settings['ADMIN_PASSWORD'], password)
            self.assertEqual(settings['ADMIN_USERNAME'], 'new-owner')
            self.assertEqual(settings['TELEGRAM_BOT_TOKEN'], '')
            self.assertGreater(len(settings['SECRET_KEY']), 40)

    def test_probe_failure_restores_database_and_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data').mkdir()
            db = root / 'data/news.db'
            with closing(sqlite3.connect(db)) as connection, connection:
                connection.execute('create table record (value text)')
                connection.execute("insert into record values ('keep')")
            source = root / 'updates/v2.3.0'
            source.mkdir(parents=True)
            (source / 'release.json').write_bytes(b'new')
            (source / 'release.sig').write_bytes(b'sig')
            (root / 'pending.txt').write_text('v2.3.0')
            (root / 'current.json').write_text('old pointer')
            manifest = {'version':'2.3.0', 'components': {'application': {'sha256': 'a'*64}}}
            def broken_probe(*args, **kwargs):
                with closing(sqlite3.connect(db)) as connection, connection:
                    connection.execute('delete from record')
                raise RuntimeError('probe failed')
            with patch.object(updater, 'read_manifest', return_value=manifest), patch.object(updater, 'current', return_value={'version':'2.2.0'}), patch.object(updater, 'install_components'), patch.object(updater.subprocess, 'run', side_effect=broken_probe):
                with self.assertRaises(RuntimeError):
                    updater.apply_pending(root, b'key')
            with closing(sqlite3.connect(db)) as connection:
                self.assertEqual(connection.execute('select value from record').fetchone()[0], 'keep')
            self.assertEqual((root / 'current.json').read_text(), 'old pointer')


if __name__ == '__main__':
    unittest.main()
