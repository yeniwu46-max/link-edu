"""One pending manual invitation; no model work or learning evidence at enqueue time."""
import random

class StudentInteractionQueue:
    def __init__(self):
        self.pending = None

    def enqueue(self, student_id, event_id):
        if student_id not in ('ming', 'yu', 'lin'):
            raise ValueError('无效学生')
        if self.pending and self.pending['student_id'] == student_id:
            return self.pending
        self.pending = dict(student_id=student_id, request_id=event_id,
                            interaction_kind=random.choice(('question', 'challenge')),
                            trigger='manual_click')
        return self.pending

    def take(self):
        value, self.pending = self.pending, None
        return value

    def clear(self):
        self.pending = None
