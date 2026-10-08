"""Fetch the pinned CC0 Kenney pack and retain only classroom animation data."""
import hashlib
import io
import json
from pathlib import Path
import struct
import urllib.request
import zipfile

URL = 'https://kenney.nl/media/pages/assets/mini-characters/bfc7e272b4-1774770718/kenney_mini-characters.zip'
ARCHIVE_SHA = '9e1d48e6d7b8479ebbe84df71eb5bd8e1b3f0da546dea641890dccc8a02d0999'
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'frontend/public/assets/models/students'


def trim_glb(data):
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + length])
    binary = data[28 + length:]
    doc['animations'] = [a for a in doc.get('animations', []) if a.get('name') in ('static', 'idle', 'emote-yes')]
    used = set()
    for mesh in doc.get('meshes', []):
        for primitive in mesh['primitives']:
            used.update(primitive.get('attributes', {}).values())
            if 'indices' in primitive:
                used.add(primitive['indices'])
            for target in primitive.get('targets', []):
                used.update(target.values())
    for skin in doc.get('skins', []):
        if 'inverseBindMatrices' in skin:
            used.add(skin['inverseBindMatrices'])
    for animation in doc['animations']:
        for sampler in animation['samplers']:
            used.update((sampler['input'], sampler['output']))
    indices = {old: new for new, old in enumerate(sorted(used))}
    accessors = [doc['accessors'][i] for i in sorted(used)]
    if any('sparse' in a for a in accessors):
        raise ValueError('Sparse accessor requires a different import pipeline')
    views = {a['bufferView'] for a in accessors if 'bufferView' in a}
    views.update(im['bufferView'] for im in doc.get('images', []) if 'bufferView' in im)
    view_indices = {old: new for new, old in enumerate(sorted(views))}
    output, buffer_views = bytearray(), []
    for i in sorted(views):
        view = dict(doc['bufferViews'][i])
        start = view.get('byteOffset', 0)
        output.extend(b'\0' * (-len(output) % 4))
        view['byteOffset'] = len(output)
        output.extend(binary[start:start + view['byteLength']])
        buffer_views.append(view)
    for accessor in accessors:
        if 'bufferView' in accessor:
            accessor['bufferView'] = view_indices[accessor['bufferView']]
    for mesh in doc.get('meshes', []):
        for primitive in mesh['primitives']:
            primitive['attributes'] = {k: indices[v] for k, v in primitive['attributes'].items()}
            if 'indices' in primitive:
                primitive['indices'] = indices[primitive['indices']]
            for target in primitive.get('targets', []):
                for key in target:
                    target[key] = indices[target[key]]
    for skin in doc.get('skins', []):
        if 'inverseBindMatrices' in skin:
            skin['inverseBindMatrices'] = indices[skin['inverseBindMatrices']]
    for animation in doc['animations']:
        for sampler in animation['samplers']:
            sampler['input'], sampler['output'] = indices[sampler['input']], indices[sampler['output']]
    for image in doc.get('images', []):
        if 'bufferView' in image:
            image['bufferView'] = view_indices[image['bufferView']]
    doc['accessors'], doc['bufferViews'] = accessors, buffer_views
    doc['buffers'] = [{'byteLength': len(output)}]
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    output.extend(b'\0' * (-len(output) % 4))
    header = struct.pack('<III', 0x46546C67, 2, 28 + len(encoded) + len(output))
    return header + struct.pack('<II', len(encoded), 0x4E4F534A) + encoded + struct.pack('<II', len(output), 0x004E4942) + output, doc


def main():
    archive = urllib.request.urlopen(URL, timeout=45).read()
    if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA:
        raise ValueError('Source pack changed; review it before updating the pinned hash')
    pack = zipfile.ZipFile(io.BytesIO(archive))
    DEST.mkdir(parents=True, exist_ok=True)
    assets = []
    for name in ('character-male-a', 'character-female-b', 'character-male-e', 'aid-glasses'):
        source_path = 'Models/GLB format/' + name + '.glb'
        original = pack.read(source_path)
        result, doc = trim_glb(original)
        for image in doc.get('images', []):
            uri = image.get('uri')
            if uri:
                if uri != 'Textures/colormap.png':
                    raise ValueError('Unexpected texture reference: ' + uri)
                target = DEST / uri
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pack.read('Models/GLB format/' + uri))
        (DEST / (name + '.glb')).write_bytes(result)
        assets.append({'file': name + '.glb', 'originalSha256': hashlib.sha256(original).hexdigest(),
                       'sha256': hashlib.sha256(result).hexdigest(), 'bytes': len(result),
                       'clips': [a['name'] for a in doc['animations']]})
        print(name, len(result))
    (DEST / 'LICENSE.txt').write_bytes(pack.read('License.txt'))
    credits = {'author': 'Kenney', 'pack': 'Mini Characters 1.0', 'source': 'https://kenney.nl/assets/mini-characters',
               'license': 'CC0-1.0', 'archiveSha256': ARCHIVE_SHA,
               'adaptations': ['Retain static, idle and emote-yes; remove unused animation data.',
                               'Runtime holographic surfaces, lighting, classroom poses and speaking gestures.'], 'assets': assets}
    (DEST / 'credits.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
