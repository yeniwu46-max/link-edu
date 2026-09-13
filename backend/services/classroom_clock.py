"""Wall-clock evidence coordinates and independently paused teaching time."""
from datetime import datetime
import threading
import uuid
from extensions import db
from classroom_models import ClassroomEvent

clock_lock = threading.RLock()


def active_seconds(events, wall_seconds):
    end = max(0, wall_seconds * 1000)
    paused_at, excluded = None, 0
    for e in sorted(events, key=lambda e: e['at_ms']):
        at = min(end, max(0, e['at_ms']))
        if e['type'] == 'pause' and paused_at is None:
            paused_at = at
        elif e['type'] == 'resume' and paused_at is not None:
            excluded += at - paused_at
            paused_at = None
    if paused_at is not None:
        excluded += end - paused_at
    return max(0, (end - excluded) / 1000)


def timing(room):
    wall = max(0, ((room.ended_at or datetime.utcnow()) - room.started_at).total_seconds())
    events = [e.to_dict() for e in ClassroomEvent.query.filter_by(session_id=room.session_id)
              .filter(ClassroomEvent.kind.in_(['pause', 'resume'])).all()]
    return dict(wall_elapsed=wall, active_elapsed=active_seconds(events, wall))


def transition(room, state, reason='teacher'):
    with clock_lock:
        db.session.refresh(room)
        if room.state == 'ended' or room.state == state:
            return False
        if state not in ('paused', 'active'):
            raise ValueError('无效课堂状态')
        kind = 'pause' if state == 'paused' else 'resume'
        at = max(0, int((datetime.utcnow() - room.started_at).total_seconds() * 1000))
        room.state = state
        db.session.add(ClassroomEvent(session_id=room.session_id, event_key=uuid.uuid4().hex,
            kind=kind, at_ms=at, payload={'reason': reason}))
        db.session.commit()
        return True
