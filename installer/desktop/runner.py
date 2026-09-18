"""Entry point for the isolated installed server (never for the source checkout)."""
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
release = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(release / 'application'))
os.chdir(release / 'application')
from dotenv import load_dotenv
load_dotenv(root / 'data' / '.env', override=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + (root / 'data' / 'news.db').as_posix()
os.environ['OTOTREND_DATA_DIR'] = str(root / 'data')
if '--probe' in sys.argv:
    os.environ['RUN_SCHEDULER'] = 'false'
    import main
    from sqlalchemy import text
    with main.engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    main.app.openapi()
    print('PROBE_OK')
else:
    import uvicorn
    import threading
    import time
    server = uvicorn.Server(uvicorn.Config('main:app', host='127.0.0.1', port=int(os.environ.get('OTOTREND_PORT', '8765'))))
    def watch_stop():
        while not server.should_exit:
            if (root / 'data' / 'stop.request').exists():
                server.should_exit = True
                return
            time.sleep(1)
    threading.Thread(target=watch_stop, daemon=True).start()
    server.run()
