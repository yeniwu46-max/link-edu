"""Package staged/tracked source and runtime assets; reject secrets before writing ZIP."""
from pathlib import Path
import hashlib, json, subprocess, zipfile
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/competition-delivery-20260914'

def source_files():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for base in ('frontend/public/models','frontend/dist'):
        names += [p.relative_to(ROOT).as_posix() for p in (ROOT/base).rglob('*') if p.is_file()]
    for rel in sorted(set(names)):
        if not rel: continue
        path=ROOT/rel
        if not path.is_file(): continue
        parts=set(path.relative_to(ROOT).parts)
        if parts & {'node_modules','.git','__pycache__','private','instance','.venv','output','artifacts'}: continue
        if path.name.startswith('.env') and not path.name.endswith('example'): continue
        if path.suffix in ('.db','.sqlite','.sqlite3','.pyc','.log'): continue
        yield rel,path

def main():
    dest=OUT/'05—作品代码'; dest.mkdir(parents=True,exist_ok=True)
    secret_values=[]
    for env in (ROOT/'backend/.env',ROOT/'artifacts/private/competition-runtime/runtime.env',ROOT/'artifacts/private/competition-runtime/mysql.env'):
        for name,value in dotenv_values(env).items():
            if value and value != 'link-demo-change-me' and len(value)>=16 and any(s in name for s in ('KEY','SECRET','PASSWORD')):
                secret_values.append(value.encode())
    manifest=[]
    archive_path=dest/'临客LINK-作品代码.zip'
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for rel,path in source_files():
            content=path.read_bytes()
            if any(secret in content for secret in secret_values): raise RuntimeError('Secret detected in '+rel)
            archive.writestr('LINK/'+rel,content)
            manifest.append({'path':rel,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
        version={'version':'competition-20260914','commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 'branch':'codex/competition-delivery-20260914','merged_branch':'gao914','merged_commit':'f83764297e9f0d57d8a0dd726f8dda220d22afd8',
                 'state':'Tracked application source is from this commit; included production build and browser models are verified separately by SHA256SUMS.',
                 'manifest_files':len(manifest)}
        archive.writestr('LINK/VERSION.json',json.dumps(version,ensure_ascii=False,indent=2))
        archive.writestr('LINK/SHA256SUMS', '\n'.join(x['sha256']+'  '+x['path'] for x in manifest)+'\n')
    with zipfile.ZipFile(archive_path) as z:
        assert z.testzip() is None
        for item in manifest: assert hashlib.sha256(z.read('LINK/'+item['path'])).hexdigest()==item['sha256']
    (dest/'源码文件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'VERSION.json').write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_files':len(manifest),'source_zip_bytes':archive_path.stat().st_size,'secret_scan':'passed','zip_crc_and_sha256':'passed'}))

if __name__=='__main__': main()
