"""Read-only, credential-free inventory of application payload candidates.

This does not create a setup, publish files, or guarantee secret-free source.
An explicit code review is required before publishing the listed source files.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_FILES = {'main.py', 'requirements.txt', 'requirements.windows.txt'}
ALLOWED_SUFFIXES = {'.py', '.html', '.css', '.js', '.json', '.svg', '.png', '.jpg', '.ico', '.woff', '.woff2'}
EXCLUDED_PARTS = {'__pycache__', 'generated', '.git', '.venv', 'logs', 'backups'}


def eligible(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        return False
    if any(part.startswith('.') or part in EXCLUDED_PARTS for part in path.parts):
        return False
    if len(path.parts) == 1:
        return path.name in ALLOWED_ROOT_FILES
    return path.parts[0] == 'app' and path.suffix.lower() in ALLOWED_SUFFIXES


def inventory(root=ROOT):
    files = []
    candidates = [root / name for name in ALLOWED_ROOT_FILES]
    candidates.extend((root / 'app').rglob('*'))
    for path in candidates:
        if not path.is_file() or any(parent.is_symlink() for parent in [path, *path.parents]):
            continue
        relative = path.relative_to(root)
        if eligible(relative):
            files.append({'path': relative.as_posix(), 'bytes': path.stat().st_size})
    return sorted(files, key=lambda entry: entry['path'])


if __name__ == '__main__':
    files = inventory()
    print(json.dumps({'setup_ready': False, 'source_file_count': len(files),
                      'source_bytes': sum(entry['bytes'] for entry in files),
                      'files': files}, ensure_ascii=False, indent=2))
