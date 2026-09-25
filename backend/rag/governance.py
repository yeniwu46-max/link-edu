"""Document governance audit trail."""
from datetime import datetime

from extensions import db


class KnowledgeAuditLog(db.Model):
    __tablename__ = 'kb_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('kb_documents.id', ondelete='SET NULL'), index=True)
    action = db.Column(db.String(32), nullable=False)
    actor_id = db.Column(db.Integer, index=True)
    detail = db.Column(db.JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'action': self.action,
            'actor_id': self.actor_id,
            'detail': self.detail or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def log_audit(document_id, action, *, actor_id=None, **detail):
    db.session.add(KnowledgeAuditLog(
        document_id=document_id, action=action, actor_id=actor_id, detail=detail or {}))
    db.session.flush()


def document_is_expired(document):
    raw = getattr(document, 'valid_until', None)
    if not raw:
        return False
    try:
        from datetime import date
        if isinstance(raw, date):
            return raw < date.today()
        return str(raw) < datetime.utcnow().strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        return False
