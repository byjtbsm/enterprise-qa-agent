import json
import re
from pathlib import Path


def tokens(text):
    text = text.lower()
    # Small local baseline: Chinese bigrams and English words; no hidden model.
    return set(re.findall(r'[a-z0-9]+', text)) | {
        text[i:i+2] for i in range(len(text)-1)
        if all('\u4e00' <= c <= '\u9fff' for c in text[i:i+2])
    }


class Tools:
    def __init__(self, documents, failures=None):
        fields = {'id', 'title', 'version_date', 'scope', 'text'}
        if not isinstance(documents, list) or not all(
            isinstance(d, dict) and fields <= set(d) and
            all(isinstance(d[k], str) and d[k].strip() for k in fields) for d in documents
        ):
            raise ValueError('documents must be a list with non-empty id/title/version_date/scope/text')
        self.docs = {d['id']: dict(d) for d in documents}
        if len(self.docs) != len(documents):
            raise ValueError('duplicate document IDs')
        self.failures = dict(failures or {})
        if any(k not in ('read', 'search') or type(v) is not int or v < 0 for k, v in self.failures.items()):
            raise ValueError('failure counts must be non-negative integers for read/search')
        self.read_evidence = {}

    @classmethod
    def load(cls, path, failures=None):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')), failures)

    def execute(self, action, args):
        if action not in ('search', 'read'):
            return {'ok': False, 'error': 'unknown_tool'}
        if self.failures.get(action, 0) > 0:
            self.failures[action] -= 1
            return {'ok': False, 'error': 'injected_tool_failure', 'retryable': True}
        if action == 'search':
            if set(args) != {'query'} or not isinstance(args['query'], str) or not args['query'].strip():
                return {'ok': False, 'error': 'invalid_search_arguments'}
            query = tokens(args['query'])
            ranked = []
            for d in self.docs.values():
                score = len(query & tokens(d['title'] + d['text']))
                if score:
                    ranked.append((score, d))
            ranked.sort(key=lambda x: (-x[0], x[1]['id']))
            return {'ok': True, 'hits': [
                {'id': d['id'], 'title': d['title'], 'version_date': d['version_date'],
                 'scope': d['scope'], 'score': score, 'preview': d['text'][:28]}
                for score, d in ranked[:8]], 'truncated': len(ranked) > 8}
        if set(args) != {'doc_id'} or not isinstance(args['doc_id'], str):
            return {'ok': False, 'error': 'invalid_read_arguments'}
        d = self.docs.get(args['doc_id'])
        if not d:
            return {'ok': False, 'error': 'document_not_found'}
        self.read_evidence[d['id']] = dict(d)
        return {'ok': True, 'document': dict(d)}
