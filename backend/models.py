from datetime import datetime

from extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='student')
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.Text)
    school = db.Column(db.String(128))
    major = db.Column(db.String(128))
    grade = db.Column(db.String(32))
    level = db.Column(db.Integer, default=1, nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)
    badges_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    training_sessions = db.relationship('TrainingSession', back_populates='user', lazy='dynamic')
    feedbacks = db.relationship('AiFeedback', back_populates='user', lazy='dynamic')
    journals = db.relationship('TrainingJournal', back_populates='user', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'account': self.account,
            'name': self.name,
            'role': self.role,
            'role_label': '师范生' if self.role == 'student' else '指导教师',
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'school': self.school,
            'major': self.major,
            'grade': self.grade,
            'level': self.level or 1,
            'xp': self.xp or 0,
            'badges': [],
        }


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    lesson_count = db.Column(db.Integer, default=0, nullable=False)
    cover_url = db.Column(db.String(255))
    stage = db.Column(db.String(32))
    outline = db.Column(db.Text)
    source = db.Column(db.String(128))
    source_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    training_sessions = db.relationship('TrainingSession', back_populates='course', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'lesson_count': self.lesson_count,
            'cover_url': self.cover_url,
            'stage': self.stage,
            'outline': self.outline,
            'source': self.source,
            'source_url': self.source_url,
        }


class TrainingSession(db.Model):
    __tablename__ = 'training_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default='in_progress')
    progress_percent = db.Column(db.Integer, default=0, nullable=False)
    duration_minutes = db.Column(db.Integer, default=0, nullable=False)
    started_at = db.Column(db.DateTime)
    last_trained_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='training_sessions')
    course = db.relationship('Course', back_populates='training_sessions')
    feedbacks = db.relationship('AiFeedback', back_populates='session', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_title': self.course.title if self.course else None,
            'category': self.course.category if self.course else None,
            'status': self.status,
            'status_label': '进行中' if self.status == 'in_progress' else '已完成',
            'progress_percent': self.progress_percent,
            'duration_minutes': self.duration_minutes,
            'last_trained_at': self.last_trained_at.isoformat() if self.last_trained_at else None,
        }


class AiFeedback(db.Model):
    __tablename__ = 'ai_feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey('training_sessions.id'), index=True)
    overall_score = db.Column(db.Integer, nullable=False)
    clarity_score = db.Column(db.Integer)
    pace_score = db.Column(db.Integer)
    interaction_score = db.Column(db.Integer)
    suggestion = db.Column(db.Text)
    report_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='feedbacks')
    session = db.relationship('TrainingSession', back_populates='feedbacks')

    def to_dict(self):
        course_title = None
        category = None
        if self.session and self.session.course:
            course_title = self.session.course.title
            category = self.session.course.category
        payload = {
            'id': self.id,
            'session_id': self.session_id,
            'course_title': course_title,
            'category': category,
            'overall_score': self.overall_score,
            'clarity_score': self.clarity_score,
            'pace_score': self.pace_score,
            'interaction_score': self.interaction_score,
            'suggestion': self.suggestion,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        from services.training import report_from_feedback_row
        report = report_from_feedback_row(self)
        if report.get('insufficient_evidence'):
            payload['overall_score'] = None
            payload['clarity_score'] = None
            payload['pace_score'] = None
            payload['interaction_score'] = None
        payload['report'] = report
        payload['mode_label'] = report.get('mode_label')
        payload['dimensions'] = report.get('dimensions') or []
        return payload


class Resource(db.Model):
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64))
    description = db.Column(db.String(255))
    file_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'file_url': self.file_url,
        }


class TrainingJournal(db.Model):
    __tablename__ = 'training_journals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    entry_date = db.Column(db.String(10), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='journals')

    def to_dict(self):
        return {
            'id': self.id,
            'entry_date': self.entry_date,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
