"""Export locked package metadata and model provenance without private configuration."""
from pathlib import Path
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
out = root / 'deploy/third-party'
out.mkdir(parents=True, exist_ok=True)
lock = json.loads((root / 'frontend/package-lock.json').read_text(encoding='utf-8'))
packages = []
for name, metadata in lock['packages'].items():
    if not name:
        continue
    packages.append({'path': name, 'version': metadata.get('version'),
                     'license': metadata.get('license', 'See upstream distribution'),
                     'resolved': metadata.get('resolved'), 'integrity': metadata.get('integrity')})
    installed = root / 'frontend' / name
    for source in installed.glob('*'):
        if source.is_file() and source.name.lower().startswith(('license', 'notice', 'copying')):
            target = out / 'licenses' / name.replace('node_modules/', '') / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
(out / 'frontend-packages.json').write_text(json.dumps(packages, indent=2), encoding='utf-8', newline='\n')
script = (root / 'scripts/prepare-pose.mjs').read_text(encoding='utf-8')
urls = re.findall(r'https://storage\.googleapis\.com/[^\s\"\']+', script)
models = []
for source in (root / 'frontend/public/models').rglob('*'):
    if source.is_file():
        models.append({'path': source.relative_to(root).as_posix(), 'bytes': source.stat().st_size,
                       'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                       'source': next((url for url in urls if url.endswith('/' + source.name)),
                                      '@mediapipe/tasks-vision distribution; exact version in npm lock')})
(out / 'browser-models.json').write_text(json.dumps(models, indent=2), encoding='utf-8', newline='\n')
print(f'Inventoried {len(packages)} frontend packages and {len(models)} browser runtime assets.')
