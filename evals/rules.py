"""Production parsers plus offline invariants; no app or database initialization."""
import json
import sys
from evals.dataset import ROOT

sys.path.insert(0, str(ROOT / 'backend'))
from services.classroom_stream import StudentDraft, unique_object, validate_student
from services.classroom_reports import validate_report, usable_visual
from services.classroom_motion import motion_evidence


def inspect_output(case, raw):
    checks = {}
    validated = None
    try:
        if case['kind'] == 'student':
            parser = StudentDraft()
            serialized = json.dumps(raw, ensure_ascii=False)
            for char in serialized:
                parser.feed(char)
            validated = validate_student(json.loads(parser.buffer, object_pairs_hook=unique_object))
            checks['student_structure'] = True
            if validated['action'] != 'wait':
                named = case['payload']['named_student']
                checks['named_student'] = not named or validated['student_id'] == named
                checks['quiet_lin'] = validated['student_id'] != 'lin' or named == 'lin'
                checks['proactive_permission'] = validated['action'] != 'raise' or case['payload']['allow_proactive']
                checks['text_length'] = len(validated['text']) <= 100
            if case['id'] == 'F26':
                checks['resolved_question_not_repeated'] = validated['action'] == 'wait'
        else:
            events, refs = case['events'], case['references']
            validated = validate_report(raw, events, refs)
            checks['report_structure'] = True
            dims = raw.get('dimensions', [])
            if isinstance(dims, dict):
                dims = list(dims.values())
            ids, sources = {e['id'] for e in events}, {s['id'] for s in refs}
            checks['references_valid'] = all(
                isinstance(d, dict) and isinstance(d.get('event_ids', []), list) and
                isinstance(d.get('source_ids', []), list) and
                all(type(i) is int and i in ids for i in d.get('event_ids', [])) and
                all(isinstance(i, str) and i in sources for i in d.get('source_ids', [])) for d in dims)
            checks['no_visual_no_posture_score'] = (bool(motion_evidence(events)['eligible_event_ids']) or any(usable_visual(e) for e in events) or
                all(d['score'] is None for d in validated['dimensions'] if d['key'] == 'posture'))
            by_key = {d['key']: d for d in validated['dimensions']}
            checks['raw_score_evidence_eligible'] = all(
                d.get('score') is None or (d.get('key') in by_key and by_key[d['key']]['score'] is not None)
                for d in (raw['dimensions'] if isinstance(raw['dimensions'], list) else
                          [dict(d, key=k) for k, d in raw['dimensions'].items()]))
            checks['no_score_without_events'] = all(
                d.get('score') is None or len(d.get('event_ids') or []) > 0
                for d in (raw['dimensions'] if isinstance(raw['dimensions'], list) else raw['dimensions'].values()))
            theory = case.get('theory_by_dimension') or {}
            if theory:
                match = True
                for d in dims:
                    if not isinstance(d, dict):
                        match = False
                        break
                    allowed = {s['id'] for s in theory.get(d.get('key'), []) if isinstance(s, dict)}
                    for sid in d.get('source_ids') or []:
                        if isinstance(sid, str) and sid.startswith('kb:') and allowed and sid not in allowed:
                            match = False
                            break
                checks['kb_refs_match_dimension'] = match
    except (ValueError, TypeError, KeyError, AttributeError):
        checks[f'{case["kind"]}_structure'] = False
    return {'raw_output': raw, 'validated_output': validated, 'checks': checks}
