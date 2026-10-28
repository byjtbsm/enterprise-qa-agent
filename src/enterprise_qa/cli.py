import argparse
import json
import sys
from pathlib import Path
from .agent import run
from .models import LiveModel, OfflineMock
from .tools import Tools
from .config import load_env


def main():
    parser = argparse.ArgumentParser(description='Evidence-first enterprise QA')
    parser.add_argument('--mode', choices=['live', 'mock'], default='live')
    parser.add_argument('--question', required=True)
    parser.add_argument('--data', default='data/documents.json')
    parser.add_argument('--history', help='JSON file: user/assistant role-content messages')
    parser.add_argument('--output', help='Save full JSON result and trace')
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--fail-search', type=int, default=0, help='Inject N initial search failures')
    parser.add_argument('--fail-read', type=int, default=0, help='Inject N initial read failures')
    args = parser.parse_args()
    try:
        if args.mode == 'live':
            load_env()
        model = LiveModel() if args.mode == 'live' else OfflineMock()
        tools = Tools.load(args.data, {'search': args.fail_search, 'read': args.fail_read})
        history = json.loads(Path(args.history).read_text(encoding='utf-8')) if args.history else []
        result = run(model, tools, args.question, history, args.max_steps)
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'configuration_error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if result['status'] in ('answered', 'needs_clarification', 'insufficient_evidence') else 1


if __name__ == '__main__':
    sys.exit(main())
