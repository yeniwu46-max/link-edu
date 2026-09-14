"""Create a deployment archive from tracked/new release code; never includes credentials."""
from pathlib import Path
import subprocess, tarfile

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
paths += [str(p.relative_to(root)).replace('\\', '/') for base in ('deploy',) for p in (root / base).rglob('*') if p.is_file()]
paths += ['backend/requirements.lock.txt', 'backend/release_admin.py', 'backend/services/public_access.py', 'backend/services/delivery_budget.py']
for base in ('frontend/dist', 'frontend/public/models'):
    paths += [p.relative_to(root).as_posix() for p in (root / base).rglob('*') if p.is_file()]
dest = root / 'artifacts/private/link-release.tar.gz'
dest.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(dest, 'w:gz') as archive:
    for rel in sorted(set(paths)):
        p = root / rel
        if not p.is_file() or not rel.startswith(('backend/', 'frontend/dist/', 'frontend/public/models/', 'deploy/')): continue
        if any(x in rel.split('/') for x in ('.env', 'instance', '__pycache__', 'private', '.venv')) or p.suffix in ('.db', '.sqlite', '.pyc'): continue
        archive.add(p, arcname=rel)
print(f'Created deployment archive: {dest.stat().st_size} bytes (no runtime secrets)')
