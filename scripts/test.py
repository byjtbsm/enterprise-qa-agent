"""Execute tests and keep the actual console output in examples/."""
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main():
    result = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    text = '$ python -m unittest discover -s tests -v\n' + result.stdout + result.stderr
    text += '\nExit code: ' + str(result.returncode) + '\n'
    (ROOT/'examples/test-results.txt').write_text(text,encoding='utf-8')
    print(text)
    return result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
