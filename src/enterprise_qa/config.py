"""Minimal .env loading: no interpolation, execution, or third-party dependency."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_KEYS = {'MODEL_API_KEY', 'MODEL_BASE_URL', 'MODEL_NAME', 'MODEL_TIMEOUT'}


def load_env(path=None):
    path = Path(path) if path else ROOT / '.env'
    if not path.exists():
        return
    for line_number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'invalid .env line {line_number}')
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if key not in CONFIG_KEYS:
            raise ValueError(f'unsupported .env key on line {line_number}')
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise ValueError(f'invalid .env quoted value on line {line_number}') from None
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if not isinstance(value, str):
            raise ValueError(f'.env value must be text on line {line_number}')
        os.environ.setdefault(key, value)
