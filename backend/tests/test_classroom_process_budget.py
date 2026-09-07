import os
import subprocess
import sys
from pathlib import Path
from test_classroom_base import app
from services.classroom_budget import status

def test_two_diagnostic_processes_cannot_overreserve(app):
    code = '''from app import app
from services.classroom_budget import reserve
with app.app_context():
    try:
        reserve('synthetic-process-test', 60)
        print('reserved')
    except ValueError:
        print('blocked')
'''
    environment = dict(os.environ, DATABASE_URL=app.config['SQLALCHEMY_DATABASE_URI'], AI_PRICING_CONFIRMED='true')
    commands = [subprocess.Popen([sys.executable,'-c',code], cwd=Path(__file__).resolve().parents[1],
        env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    outcomes=[p.communicate(timeout=10)[0].strip() for p in commands]
    assert sorted(outcomes)==['blocked','reserved']
    assert status()['spent_and_reserved_cny']==60
