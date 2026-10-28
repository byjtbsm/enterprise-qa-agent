"""Print submission metadata only after local evidence and remote main are verified."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit import main as audit_main


def git(*args):
    env = dict(os.environ)
    env['GIT_TERMINAL_PROMPT'] = '0'
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True,
                                   stderr=subprocess.DEVNULL,timeout=30).strip()


def main():
    if audit_main(['--require-live','--require-personal']):
        return 1
    try:
        if git('status','--porcelain'):
            print('Uncommitted files found. Commit and push all deliverables before generating submission information.')
            return 1
        head = git('rev-parse','HEAD')
        remote = git('remote','get-url','origin')
        match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?',remote)
        if not match:
            print('origin must point to your actual GitHub repository (without credentials in its URL).')
            return 1
        remote_lines = git('ls-remote','origin','refs/heads/main').splitlines()
        if not remote_lines or remote_lines[0].split()[0] != head:
            print('Remote main does not match local HEAD. Pull if needed, then push and rerun.')
            return 1
        payload={'题号':3,'GitHub URL':'https://github.com/'+match.group(1),'最终 commit SHA':head,
                 '说明':'自动核查完成；个人贡献和语义复核声明仍由候选人负责。'}
        text=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'
        (ROOT/'submission.txt').write_text(text,encoding='utf-8')
        print(text)
        return 0
    except (OSError,subprocess.SubprocessError):
        print('Could not verify GitHub remote. Check Git installation, authentication, repository permissions, and network.')
        return 1

if __name__=='__main__':
    raise SystemExit(main())
