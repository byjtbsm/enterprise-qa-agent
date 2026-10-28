"""Interactive local setup. Never print or commit credentials."""
import getpass
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from enterprise_qa.models import LiveModel
from enterprise_qa.config import load_env


def main():
    target = ROOT / '.env'
    if target.exists():
        print('.env already exists. Edit it locally to change configuration; it was not overwritten.')
        return 1
    print('Enter your provider base URL (API prefix included), model name, and API key.')
    base = input('MODEL_BASE_URL: ').strip()
    name = input('MODEL_NAME: ').strip()
    key = getpass.getpass('MODEL_API_KEY (hidden): ').strip()
    if not all((base, name, key)):
        print('All three values are required. No configuration saved.')
        return 2
    values = {'MODEL_BASE_URL': base, 'MODEL_NAME': name, 'MODEL_API_KEY': key, 'MODEL_TIMEOUT':'45'}
    with target.open('x', encoding='utf-8') as stream:
        stream.write('# Local secrets: ignored by git. Do not share this file.\n')
        for k, v in values.items():
            stream.write(k + '=' + json.dumps(v, ensure_ascii=False) + '\n')
    target.chmod(0o600)
    try:
        load_env()
        LiveModel()
    except ValueError as exc:
        print('Saved locally, but configuration is invalid:', exc)
        return 2
    print('Configuration saved. Run: python scripts/evaluate.py --mode live')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
