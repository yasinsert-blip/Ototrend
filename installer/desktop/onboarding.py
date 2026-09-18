"""Loopback-only first-run settings; no shared default password."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
from pathlib import Path
import secrets
import threading
import urllib.parse
import webbrowser


def configure(root):
    target = Path(root) / 'data' / '.env'
    if target.exists():
        return
    nonce = secrets.token_urlsafe(32)
    completed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            content = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path != '/' + nonce:
                return self.reply(404, 'Bulunamadı')
            self.reply(200, '''<!doctype html><meta charset="utf-8"><title>OtoTrend ilk kurulum</title>
<style>body{font:18px Arial;max-width:620px;margin:40px auto;padding:20px}input{display:block;width:95%;padding:12px;margin:10px 0}button{padding:14px}</style>
<h1>OtoTrend ilk kurulum</h1><p>Ayarlar yalnızca bu bilgisayarda saklanır. Telegram bilgileri isteğe bağlıdır; boşken bildirim gönderilmez.</p>
<form method="post"><label>Yönetici adı<input name="username" required minlength="3" maxlength="64" autocomplete="username"></label>
<label>Yeni parola (en az 12 karakter)<input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>
<label>Telegram bot anahtarı<input name="telegram_token" type="password" autocomplete="off"></label>
<label>Telegram sohbet kimliği<input name="telegram_chat" autocomplete="off"></label>
<button>Kaydet ve başlat</button></form>''')

        def do_POST(self):
            if self.path != '/' + nonce or self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                return self.reply(403, 'Geçersiz istek')
            if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}'):
                return self.reply(403, 'Geçersiz kaynak')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192:
                    raise ValueError()
                values = urllib.parse.parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True)
                get = lambda key: values.get(key, [''])[0]
                username, password = get('username').strip(), get('password')
                if not 3 <= len(username) <= 64 or not 12 <= len(password) <= 128:
                    raise ValueError()
                settings = {'APP_ENV': 'desktop', 'ADMIN_USERNAME': username, 'ADMIN_PASSWORD': password,
                            'SECRET_KEY': secrets.token_urlsafe(48), 'AI_PROVIDER': 'ollama',
                            'OLLAMA_MODEL': 'gemma3:4b', 'OLLAMA_HOST': 'http://127.0.0.1:11435',
                            'TELEGRAM_BOT_TOKEN': get('telegram_token').strip(),
                            'TELEGRAM_CHAT_ID': get('telegram_chat').strip(),
                            'AI_TIMEOUT': '120', 'MAX_CONTENT_LENGTH': '800',
                            'AI_BATCH_SIZE': '1', 'AI_WORKER_INTERVAL_SECONDS': '150',
                            'OLLAMA_NUM_CTX': '1024', 'OLLAMA_NUM_PREDICT': '120',
                            'AI_TURKISH_QUALITY_RETRIES': '1'}
                if any('\n' in v or '\r' in v or '\x00' in v for v in settings.values()):
                    raise ValueError()
                # python-dotenv single-quote escaping; credentials never enter process arguments.
                text = '\n'.join(k + "='" + v.replace('\\', '\\\\').replace("'", "\\'") + "'" for k, v in settings.items()) + '\n'
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8') as out:
                    out.write(text)
                self.reply(200, '<h1>Ayarlar kaydedildi</h1><p>Uygulama açılıyor. İlk AI başlangıcı birkaç dakika sürebilir.</p>')
                completed.set()
            except (ValueError, UnicodeError, FileExistsError):
                self.reply(400, 'Bilgiler geçersiz veya daha önce kaydedildi. Geri dönüp kontrol edin.')

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        server.timeout = 1
        webbrowser.open(f'http://127.0.0.1:{server.server_port}/{nonce}')
        for _ in range(1800):
            server.handle_request()
            if completed.is_set():
                return
    raise RuntimeError('İlk kurulum tamamlanmadı')
