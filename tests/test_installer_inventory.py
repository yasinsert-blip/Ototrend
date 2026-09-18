import unittest
from scripts.installer_inventory import eligible


class InstallerInventoryTests(unittest.TestCase):
    def test_source_allowlist(self):
        for name in ('main.py', 'requirements.windows.txt', 'app/config.py', 'app/templates/editor.html'):
            self.assertTrue(eligible(name), name)

    def test_private_and_runtime_files_excluded(self):
        for name in ('.env', '.env.example', 'news.db', 'logs/server.log',
                     'app/static/generated/image.png', 'app/.env', 'app/news.db',
                     'app/__pycache__/x.pyc', '../app/config.py',
                     'backups/main.py', '.venv/main.py'):
            self.assertFalse(eligible(name), name)
