"""Additive tables: old demo feedbacks remain untouched."""
from datetime import datetime
from extensions import db


class Classroom(db.Model):
    __tablename__ = 'classrooms'
    session_id = db.Column(db.Integer, db.ForeignKey('training_sessions.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    mode = db.Column(db.String(16), nullable=False, default='full')
    topic = db.Column(db.String(128), default='分数的初步认识', nullable=False)
    state = db.Column(db.String(24), default='active', nullable=False)
    students = db.Column(db.JSON, default=dict, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime)
    cloud_vision = db.Column(db.Boolean, default=False, nullable=False)
    report_state = db.Column(db.String(24), default='idle', nullable=False)
    report = db.Column(db.JSON)
    report_error = db.Column(db.String(160))
    report_version = db.Column(db.Integer, default=0, nullable=False)
    correction = db.Column(db.Text, default='')


class ClassroomEvent(db.Model):
    __tablename__ = 'classroom_events'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('classrooms.session_id'), nullable=False, index=True)
    event_key = db.Column(db.String(96), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    at_ms = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint('session_id', 'event_key'),)

    def to_dict(self):
        return dict(id=self.id, session_id=self.session_id, type=self.kind,
                    at_ms=self.at_ms, data=self.payload)


class ApiUsage(db.Model):
    __tablename__ = 'classroom_api_usage'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, index=True)
    service = db.Column(db.String(20), nullable=False)
    reserved_cny = db.Column(db.Float, nullable=False)
    charged_cny = db.Column(db.Float)
    units = db.Column(db.JSON, default=dict)
    state = db.Column(db.String(20), default='reserved', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CreditUsage(db.Model):
    """OpenAI Next USD estimates; never mix these with the historical CNY ledger."""
    __tablename__ = 'classroom_credit_usage'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(16), nullable=False, index=True)
    service = db.Column(db.String(16), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    session_id = db.Column(db.Integer, index=True)
    reserved_usd = db.Column(db.Float, nullable=False)
    charged_usd = db.Column(db.Float)
    units = db.Column(db.JSON, default=dict)
    state = db.Column(db.String(20), default='reserved', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ClassroomTicket(db.Model):
    __tablename__ = 'classroom_tickets'
    digest = db.Column(db.String(64), primary_key=True)
    session_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
