import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from bundle import current, component_path


def notify(message):
    ctypes.windll.user32.MessageBoxW(None, message, 'OtoTrend AI', 0)


def main():
    root = Path(sys.argv[1]).resolve()
    data = root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    # Byte-range lock is released even if Windows terminates the process.
    import msvcrt
    lock = (data / 'instance.lock').open('a+b')
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        notify('OtoTrend zaten açık. Tarayıcıdan http://127.0.0.1:8765 adresine ulaşabilirsiniz.')
        return
    key = Path(__file__).with_name('public-key.xml').read_bytes()
    (data / 'stop.request').unlink(missing_ok=True)
    from onboarding import configure
    configure(root)
    logs = data / 'logs'
    logs.mkdir(exist_ok=True)
    from updater import stage_update, apply_pending
    # Background checks never stop the running server or change its current release.
    def update_check():
        try:
            stage_update(root, key)
        except Exception as error:
            with (logs / 'updater.log').open('a', encoding='utf-8') as stream:
                stream.write(time.strftime('%Y-%m-%d %H:%M:%S ') + type(error).__name__ + '\n')
    try:
        if apply_pending(root, key):
            notify('Yeni sürüm kuruldu. Verileriniz yedeklendi ve korundu.')
    except Exception:
        notify('Güncelleme uygulanamadı. Önceki sürümle devam ediliyor; verileriniz korundu.')
    manifest = current(root, key)
    application = component_path(root, 'application', manifest['components']['application'])
    tools = component_path(root, 'tools', manifest['components']['tools'])
    models = component_path(root, 'models', manifest['components']['models'])
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(tools / 'browsers'),
               OLLAMA_MODELS=str(models / 'models'), OLLAMA_HOST='127.0.0.1:11435',
               OLLAMA_NO_CLOUD='1', PYTHONUTF8='1', OTOTREND_DATA_DIR=str(data))
    # Never attach to or terminate another application's server/model process.
    for port in (8765, 11435):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                notify(f'{port} bağlantısı başka bir uygulama tarafından kullanılıyor. Mevcut OtoTrend kopyasını kapatıp tekrar deneyin.')
                return
    with (logs / 'ollama.log').open('a', encoding='utf-8') as ollama_log, (logs / 'server.log').open('a', encoding='utf-8') as server_log:
        model = subprocess.Popen([str(tools / 'ollama' / 'ollama.exe'), 'serve'], env=env, stdout=ollama_log, stderr=ollama_log, creationflags=0x08000000)
        server = None
        try:
            for _ in range(30):
                if model.poll() is not None:
                    raise RuntimeError('Yerel AI başlatılamadı')
                try:
                    urllib.request.urlopen('http://127.0.0.1:11435/api/tags', timeout=1).close()
                    break
                except OSError:
                    time.sleep(1)
            server = subprocess.Popen([str(application / 'runtime' / 'python.exe'), str(application / 'desktop' / 'runner.py'), str(root)],
                                      env=env, stdout=server_log, stderr=server_log, creationflags=0x08000000)
            ready = False
            for _ in range(240):
                if server.poll() is not None:
                    raise RuntimeError('Uygulama başlatılamadı; data/logs/server.log kaydını kontrol edin')
                try:
                    urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=1).close()
                    ready = True
                    break
                except OSError:
                    time.sleep(1)
            if not ready:
                raise RuntimeError('Uygulama başlangıç süresi aşıldı')
            webbrowser.open('http://127.0.0.1:8765')
            threading.Thread(target=update_check, daemon=True).start()
            last_check = time.monotonic()
            while server.poll() is None:
                time.sleep(2)
                if time.monotonic() - last_check >= 6 * 3600:
                    threading.Thread(target=update_check, daemon=True).start()
                    last_check = time.monotonic()
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                server.wait(timeout=30)
            model.terminate()
            model.wait(timeout=30)
    lock.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        notify(str(error))
