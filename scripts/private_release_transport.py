"""Operator-only staging: reads local credentials without printing their values."""
from pathlib import Path
from datetime import datetime, timezone
import secrets
import paramiko
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
private = root / 'artifacts/private/competition-runtime'
private.mkdir(parents=True, exist_ok=True)
source = dotenv_values(root / 'backend/.env')
if not (private / 'runtime.env').exists():
    allowed = ('OPENAI_NEXT_', 'XFYUN_', 'DEEPSEEK_', 'DASHSCOPE_', 'BAILIAN_', 'AI_', 'SPEECH_')
    values = {k: v for k, v in source.items() if k.startswith(allowed) and v is not None}
    password = secrets.token_hex(24)
    values.update(PUBLIC_DEPLOYMENT='true', PUBLIC_ORIGINS='https://106.15.77.40:8443,https://www.lk.link-edu.cn',
                  JWT_SECRET_KEY=secrets.token_urlsafe(64), SEED_ON_STARTUP='false',
                  DATABASE_URL=f'mysql+pymysql://link:{password}@db:3306/link?charset=utf8mb4',
                  CLASSROOM_MAX_ACTIVE='5', CLASSROOM_DAILY_LIMIT='2',
                  DELIVERY_BUDGET_CNY='30', DELIVERY_BUDGET_START=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                  USD_CNY_BUDGET_RATE='8', CLASSROOM_LLM_PROVIDER=source.get('CLASSROOM_LLM_PROVIDER', 'openai_next'))
    for v in values.values():
        if '\n' in v or '\r' in v: raise ValueError('Multiline runtime value unsupported')
    (private / 'runtime.env').write_text('\n'.join(f'{k}={v}' for k, v in values.items())+'\n', encoding='utf-8')
    (private / 'mysql.env').write_text(f'MYSQL_DATABASE=link\nMYSQL_USER=link\nMYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={secrets.token_hex(32)}\n', encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.connect('106.15.77.40', username='root', key_filename=str(Path.home()/'.ssh/plex_ecs'), timeout=20)
_, stdout, stderr = ssh.exec_command('mkdir -p /opt/link-demo/releases/20260914 /opt/link-demo/shared && chmod 700 /opt/link-demo/shared')
assert stdout.channel.recv_exit_status() == 0
sftp = ssh.open_sftp()
sftp.put(str(root/'artifacts/private/link-release.tar.gz'), '/opt/link-demo/releases/20260914/release.tar.gz')
for name in ('runtime.env', 'mysql.env'):
    sftp.put(str(private/name), '/opt/link-demo/shared/'+name)
    sftp.chmod('/opt/link-demo/shared/'+name, 0o600)
sftp.close()
_, stdout, stderr = ssh.exec_command('cd /opt/link-demo/releases/20260914 && tar -xzf release.tar.gz && chmod +x deploy/*.sh')
assert stdout.channel.recv_exit_status() == 0, stderr.read().decode()
ssh.close()
print('Release and private runtime transferred to isolated server directories.')
