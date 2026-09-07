"""Loopback, single-process classroom backend. Never enable multiple workers."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import app,init_db
parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=5001)
args=parser.parse_args()
if not 1024<=args.port<=65535:
    parser.error('Port must be 1024..65535')
from services.classroom_locks import claim_server
claim_server()
init_db()
app.run(host='127.0.0.1',port=args.port,debug=False,threaded=True)
