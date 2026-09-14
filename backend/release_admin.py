"""Explicit schema/catalog setup. Never creates demonstration users or feedback."""
import argparse
import uuid
from sqlalchemy import func
from app import app, init_db
from extensions import db
from seed import ensure_demo_catalog
from classroom_models import Classroom, ClassroomEvent, ClassroomTicket


def initialize():
    init_db()
    with app.app_context():
        ensure_demo_catalog()
        from datetime import datetime
        ClassroomTicket.query.filter(ClassroomTicket.expires_at < datetime.utcnow()).delete()
        db.session.commit()
        print('Schema and public course/resource catalog ready; no demo accounts created.')


def recover():
    with app.app_context():
        for room in Classroom.query.filter_by(state='active').all():
            at = db.session.query(func.max(ClassroomEvent.at_ms)).filter_by(session_id=room.session_id).scalar() or 0
            db.session.add(ClassroomEvent(session_id=room.session_id, event_key=uuid.uuid4().hex,
                kind='pause', at_ms=at, payload={'reason': 'server_restart'}))
            room.state = 'paused'
        for room in Classroom.query.filter_by(report_state='running').all():
            room.report_state = 'failed'
            room.report_error = '服务重启中断了报告任务，请重试'
        db.session.commit()
        print('Interrupted rooms paused at last saved evidence; interrupted reports can be retried.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'recover'])
    args = parser.parse_args()
    initialize() if args.command == 'init' else recover()
