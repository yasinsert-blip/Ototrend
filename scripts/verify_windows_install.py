"""Exercise the real offline payload in an isolated test directory.

Never uses the development database, Telegram credentials or production ports.
Leaves the test installation for inspection; removes no user files.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer/desktop'))
from bundle import current, component_path


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--browser-only', action='store_true')
    args = parser.parse_args()
    if args.browser_only:
        from playwright.sync_api import sync_playwright
        url = os.environ['OTOTREND_TEST_URL']
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            requests = []
            def route_request(route):
                if route.request.url.startswith(url):
                    route.continue_()
                else:
                    requests.append(route.request.url)
                    route.abort()
            page.route('**/*', route_request)
            page.goto(url + '/login')
            page.locator('input[name="username"]').fill('installer-test')
            page.locator('input[name="password"]').fill(os.environ['OTOTREND_TEST_PASSWORD'])
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state('networkidle')
            page.goto(url + '/editor', wait_until='networkidle')
            assert page.locator('#news-status').is_visible()
            assert not requests, 'Unexpected external UI dependencies'
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(args.target / 'offline-editor.png'), full_page=True)
            browser.close()
        print('OFFLINE_BROWSER_OK', flush=True)
        return
    target = args.target.resolve()
    allowed = (ROOT / 'build').resolve()
    if not target.is_relative_to(allowed) or target == allowed or target.exists():
        raise ValueError('Use a new test folder strictly below project/build')
    bootstrap = allowed / ('bootstrap-' + target.name)
    bootstrap.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(ROOT / 'installer/vendor/bootstrap.zip') as archive:
        archive.extractall(bootstrap)
    subprocess.run([str(bootstrap / 'runtime/python.exe'), str(bootstrap / 'desktop/install.py'),
                    '--source', str(args.release.resolve()), '--root', str(target), '--no-shortcuts'], check=True)
    key = (ROOT / 'installer/desktop/public-key.xml').read_bytes()
    manifest = current(target, key)
    application = component_path(target, 'application', manifest['components']['application'])
    tools = component_path(target, 'tools', manifest['components']['tools'])
    models = component_path(target, 'models', manifest['components']['models'])
    data = target / 'data'
    data.mkdir()
    password = secrets.token_urlsafe(24)
    # Synthetic settings only. No Telegram or external AI connections.
    (data / '.env').write_text('APP_ENV=desktop\nADMIN_USERNAME=installer-test\nADMIN_PASSWORD=' + password + '\nSECRET_KEY=' + secrets.token_urlsafe(48) + '\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\nAI_PROVIDER=ollama\nRUN_SCHEDULER=false\n', encoding='utf-8')
    python = application / 'runtime/python.exe'
    runner = application / 'desktop/runner.py'
    env = dict(os.environ, PYTHONUTF8='1', PLAYWRIGHT_BROWSERS_PATH=str(tools / 'browsers'))
    subprocess.run([str(python), str(runner), str(target), '--probe'], env=env, check=True, timeout=120)
    port = free_port()
    env['OTOTREND_PORT'] = str(port)
    env['OTOTREND_TEST_URL'] = f'http://127.0.0.1:{port}'
    env['OTOTREND_TEST_PASSWORD'] = password
    flags = 0x08000000 if os.name == 'nt' else 0
    with (target / 'smoke-server.log').open('w', encoding='utf-8') as log:
        server = subprocess.Popen([str(python), str(runner), str(target)], env=env, stdout=log, stderr=log, creationflags=flags)
        try:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError('Isolated server exited; inspect smoke-server.log')
                try:
                    result = json.load(urllib.request.urlopen(env['OTOTREND_TEST_URL'] + '/api/health', timeout=1))
                    assert result['status'] == 'ok'
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError('Isolated server health timed out')
            subprocess.run([str(python), str(Path(__file__).resolve()), '--release', str(args.release), '--target', str(target), '--browser-only'], env=env, check=True, timeout=120)
        finally:
            (data / 'stop.request').write_text('stop')
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=10)
    # Validate the bundled Ollama executable and offline model registration on a private port.
    aiport = free_port()
    env.update(OLLAMA_HOST=f'127.0.0.1:{aiport}', OLLAMA_MODELS=str(models / 'models'), OLLAMA_NO_CLOUD='1')
    with (target / 'smoke-ollama.log').open('w', encoding='utf-8') as log:
        model = subprocess.Popen([str(tools / 'ollama/ollama.exe'), 'serve'], env=env, stdout=log, stderr=log, creationflags=flags)
        try:
            for _ in range(30):
                if model.poll() is not None:
                    raise RuntimeError('Bundled Ollama failed')
                try:
                    result = json.load(urllib.request.urlopen(f'http://127.0.0.1:{aiport}/api/tags', timeout=1))
                    assert any(item['name'] == 'gemma3:4b' for item in result['models'])
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError('Bundled model registration timed out')
            print('OFFLINE_MODEL_REGISTERED', flush=True)
        finally:
            model.terminate()
            model.wait(timeout=15)
    print('ISOLATED_INSTALL_OK: ' + str(target), flush=True)


if __name__ == '__main__':
    main()
