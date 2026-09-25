"""Knowledge-base tables. Vectors live in kb_chunks so the MySQL backup is the single source of truth;
in-memory indexes are caches rebuilt from these rows."""
from datetime import datetime

from extensions import db
from rag.settings import CATEGORIES, FILE_TYPES


class KnowledgeDocument(db.Model):
    __tablename__ = 'kb_documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(16), nullable=False)
    category = db.Column(db.String(32), nullable=False, index=True)
    tags = db.Column(db.JSON, default=list, nullable=False)
    source = db.Column(db.String(255))
    description = db.Column(db.Text)
    sha256 = db.Column(db.String(64), nullable=False, unique=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    storage_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='processing', index=True)
    error = db.Column(db.String(255))
    page_count = db.Column(db.Integer)
    chunk_count = db.Column(db.Integer, default=0, nullable=False)
    embedding_model = db.Column(db.String(128))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    content_version = db.Column(db.String(32), default='1', nullable=False)
    license_note = db.Column(db.String(255))
    valid_until = db.Column(db.String(10))
    last_audited_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    chunks = db.relationship('KnowledgeChunk', back_populates='document', lazy='dynamic',
                             cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_type_label': FILE_TYPES.get(self.file_type, self.file_type),
            'category': self.category,
            'category_label': CATEGORIES.get(self.category, self.category),
            'tags': self.tags or [],
            'source': self.source,
            'description': self.description,
            'size_bytes': self.size_bytes,
            'status': self.status,
            'error': self.error,
            'page_count': self.page_count,
            'chunk_count': self.chunk_count,
            'embedding_model': self.embedding_model,
            'is_active': self.is_active,
            'uploaded_by': self.uploaded_by,
            'content_version': self.content_version or '1',
            'license_note': self.license_note,
            'valid_until': self.valid_until,
            'last_audited_at': self.last_audited_at.isoformat() if self.last_audited_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class KnowledgeChunk(db.Model):
    __tablename__ = 'kb_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('kb_documents.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    ordinal = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(16), nullable=False, default='text')
    text = db.Column(db.Text, nullable=False)
    heading_path = db.Column(db.JSON, default=list, nullable=False)
    page_start = db.Column(db.Integer)
    page_end = db.Column(db.Integer)
    char_count = db.Column(db.Integer, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    embedding = db.Column(db.LargeBinary, nullable=False)
    embedding_model = db.Column(db.String(128), nullable=False, index=True)
    embedding_dim = db.Column(db.Integer, nullable=False)
    # Reserved for knowledge-graph entities/relations and judge annotations.
    extra = db.Column(db.JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    document = db.relationship('KnowledgeDocument', back_populates='chunks')

    __table_args__ = (db.UniqueConstraint('document_id', 'ordinal', name='uq_kb_chunk_ordinal'),)

    @property
    def section(self):
        return ' > '.join(self.heading_path or [])

    def to_dict(self, include_text=True, include_extra=False):
        payload = {
            'id': self.id,
            'document_id': self.document_id,
            'ordinal': self.ordinal,
            'kind': self.kind,
            'heading_path': self.heading_path or [],
            'section': self.section,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'char_count': self.char_count,
        }
        if include_text:
            payload['text'] = self.text
        if include_extra:
            payload['extra'] = self.extra or {}
        return payload
