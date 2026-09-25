"""Background ingest to avoid blocking the HTTP worker on large PDFs."""
import threading

from extensions import db
from rag.models import KnowledgeDocument


def schedule_ingest(app, kb, *, data, filename, user_id, fields, on_done=None):
    """Returns document dict snapshot; worker completes ingest in a background thread."""
    document = kb.create_processing_document(data, filename, user_id=user_id, **fields)
    db.session.commit()
    brief = document.to_dict()
    doc_id = document.id

    def worker():
        with app.app_context():
            from rag.service import get_kb
            from rag.embeddings import EmbeddingError
            from rag.parsing import ParseError
            try:
                get_kb().finish_ingest(doc_id, data)
            except (ParseError, EmbeddingError, ValueError) as error:
                row = db.session.get(KnowledgeDocument, doc_id)
                if row:
                    row.status, row.error = 'failed', str(error)[:255]
                    db.session.commit()
            except Exception as error:
                db.session.rollback()
                row = db.session.get(KnowledgeDocument, doc_id)
                if row:
                    row.status, row.error = 'failed', str(error)[:255]
                    db.session.commit()
            finally:
                if on_done:
                    on_done(doc_id)

    threading.Thread(target=worker, daemon=True).start()
    return brief
