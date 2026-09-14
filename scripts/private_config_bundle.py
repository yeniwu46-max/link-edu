"""Encrypt/decrypt owner-only configuration. Never prints credentials or the password."""
import argparse, io, secrets, zipfile
from pathlib import Path
from getpass import getpass
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'LINKCFG1'
def key(password,salt):
    return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['encrypt','decrypt'])
    parser.add_argument('--file',type=Path)
    args=parser.parse_args()
    if args.mode=='decrypt':
        if not args.file: parser.error('--file required')
        raw=args.file.read_bytes()
        if not raw.startswith(MAGIC): raise ValueError('Invalid encrypted package')
        plain=AESGCM(key(getpass('Password: '),raw[8:24])).decrypt(raw[24:36],raw[36:],MAGIC)
        target=args.file.with_suffix('.zip')
        if target.exists(): raise FileExistsError(target)
        target.write_bytes(plain); print('Decrypted ZIP written beside encrypted package. Keep it private.')
        return
    root=Path(__file__).resolve().parents[1]
    owner=root/'output/competition-private-20260914'; owner.mkdir(parents=True,exist_ok=True)
    password=secrets.token_urlsafe(32); salt=secrets.token_bytes(16); nonce=secrets.token_bytes(12)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.write(root/'backend/.env','local-original.env')
        for name in ('runtime.env','mysql.env'):
            z.write(root/'artifacts/private/competition-runtime'/name,'server/'+name)
        z.writestr('README.txt','Owner only. local-original.env preserves original API configuration. server/runtime.env is the deployed configuration; mysql.env contains isolated database credentials. Do not submit this package or decrypted files to competition platforms, Git, or frontend hosting. No SSH private key or production user database is included.')
    plain=buffer.getvalue(); encrypted=MAGIC+salt+nonce+AESGCM(key(password,salt)).encrypt(nonce,plain,MAGIC)
    target=owner/'临客LINK-私有API配置.enc'; target.write_bytes(encrypted)
    password_path=root/'artifacts/private/交付配置解密密码.txt'
    password_path.write_text(password+'\n',encoding='utf-8')
    assert AESGCM(key(password,salt)).decrypt(nonce,encrypted[36:],MAGIC)==plain
    (owner/'解密说明.txt').write_text('此目录不要提交赛事。\n1. 安装 Python 和 cryptography：python -m pip install cryptography\n2. 运行：python private_config_bundle.py decrypt --file 临客LINK-私有API配置.enc\n3. 从单独交付的密码文件输入密码；不要将密码与加密文件一起发送给第三方。\n已执行加密后解密一致性检查。\n',encoding='utf-8')
    import shutil
    shutil.copyfile(__file__,owner/'private_config_bundle.py')
    print('Encrypted owner package verified; password stored separately in artifacts/private.')

if __name__=='__main__': main()
