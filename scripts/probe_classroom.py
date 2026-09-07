"""Budgeted synthetic probes only. Never uses a microphone or private classroom data."""
import argparse
import json
import sys
import time
import httpx
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import app, init_db
from flask_jwt_extended import create_access_token
from models import User
from services.classroom_budget import status

parser = argparse.ArgumentParser()
parser.add_argument('services', nargs='*', default=['dialogue', 'vision'])
parser.add_argument('--port', type=int, default=5001)
args = parser.parse_args()
init_db()
with app.app_context():
    user = User.query.first()
    if not user:
        raise SystemExit('Create a local account before probing')
    headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(user.id))}
    for service in args.services:
        started = time.monotonic()
        result = httpx.post(f'http://127.0.0.1:{args.port}/api/classroom/probe', json={'service': service}, headers=headers, timeout=60)
        print(json.dumps({'service': service, 'result': result.json(),
                          'seconds': round(time.monotonic() - started, 3), 'budget': status()}, ensure_ascii=True))
