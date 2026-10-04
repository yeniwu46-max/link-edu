"""Versioned simulated knowledge; never a score or proof of learning."""
from copy import deepcopy
import re
from services.classroom_scenarios import FRACTIONS, supported_concepts

IDS = ('ming', 'yu', 'lin')
NAMES = {'小明': 'ming', '小雨': 'yu', '小林': 'lin'}
INTENTS = {'named_question', 'class_question', 'invite', 'resume', 'rhetorical', 'self_talk', 'lecture', 'address'}


def normalize_states(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for sid in IDS:
        old = raw.get(sid) if isinstance(raw.get(sid), dict) else {}
        initial = FRACTIONS['students'][sid]['initial_misconceptions']
        old_misconceptions = old.get('misconceptions') if isinstance(old.get('misconceptions'), list) else []
        if sid == 'yu' and '可能混淆平均分与分母大小' in old_misconceptions:
            old_misconceptions = [FRACTIONS['concepts']['equal_parts']['misconception']
                                  if value == '可能混淆平均分与分母大小' else value for value in old_misconceptions]
        concept_states = old.get('concept_states') if isinstance(old.get('concept_states'), dict) else {}
        concept_states = {key: concept_states.get(key, 'misconception' if
                          (not old and key in initial) or FRACTIONS['concepts'][key]['misconception'] in old_misconceptions
                          else 'unknown')
                          for key in FRACTIONS['concepts']}
        result[sid] = dict(version=2, understanding=old.get('understanding', ''),
            concepts=old.get('concepts', []), misconceptions=(old_misconceptions if old else
                [FRACTIONS['concepts'][key]['misconception'] for key in initial]),
            concept_states=concept_states,
            correction_event_ids=old.get('correction_event_ids', []),
            open_question=old.get('open_question', ''), interrupted=old.get('interrupted'),
            interaction_state=old.get('interaction_state', 'waiting'))
    return deepcopy(result)


def route_intent(text, carried=None, interrupted=None):
    text = str(text).strip()
    names = [(text.rfind(name), sid) for name, sid in NAMES.items() if name in text]
    named = max(names)[1] if names else None
    compact = re.sub(r'[\s，,。！!？?]', '', text)
    if re.search(r'我(?:想想|想一下|在想|自言自语)|让我想', text):
        intent = 'self_talk'
    elif re.search(r'难道|岂不是|何尝|不是[^。！？?!，,\n]*(?:吗|么)[。！？?!\s]*$', text):
        intent = 'rhetorical'
    elif re.fullmatch(r'(?:小明|小雨|小林)?(?:同学)?(?:请|你)?(?:继续|接着)(?:说|回答|讲)?(?:吧)?', compact):
        intent, named = 'resume', named or interrupted
    elif compact in NAMES or re.fullmatch(r'(?:请)?(?:小明|小雨|小林)(?:同学)?', compact):
        intent = 'address'
    elif re.search(r'请(?:你)?(?:说|讲|回答|解释)|你说|说吧|有什么问题|(?:小明|小雨|小林)(?:同学)?(?:你)?(?:来)?(?:回答|说说|解释)', text):
        intent, named = 'invite', named or carried
    elif re.search(r'[?？]|(?:吗|呢)[。！!\s]*$|谁(?:能|来|知道)|说说|回答一下', text):
        named = named or carried
        intent = 'named_question' if named else 'class_question'
    else:
        intent = 'lecture'
    return {'intent': intent, 'student_id': named,
            'response_required': intent in ('named_question', 'class_question', 'invite', 'resume') and
                (intent != 'resume' or named is not None)}


def apply_updates(states, updates, events):
    result = deepcopy(states)
    if not isinstance(updates, list):
        return result
    # An ID must refer to substantive, finalized teaching, not model prose.
    valid = {e['id'] for e in events if e.get('type') == 'transcript' and
             len(re.sub(r'\W', '', e.get('data', {}).get('text', ''))) >= 12 and
             not re.fullmatch(r'[\s，。！？?!]*(?:不对|懂了吗|明白了吗)[\s，。！？?!]*', e['data']['text'])}
    event_by_id = {e['id']: e for e in events if e.get('id') in valid}
    for update in updates[:3]:
        if not isinstance(update, dict) or update.get('student_id') not in IDS:
            continue
        refs = update.get('correction_event_ids')
        if not isinstance(refs, list) or not refs or len(refs) > 8 or any(type(i) is not int or i not in valid for i in refs):
            continue
        if not isinstance(update.get('understanding'), str) or not update['understanding'].strip():
            continue
        if any(not isinstance(update.get(k), list) or len(update[k]) > 8 or
               any(not isinstance(x, str) or len(x) > 150 for x in update[k]) for k in ('concepts', 'misconceptions')):
            continue
        supported = set().union(*(supported_concepts(event_by_id[ref]['data']['text']) for ref in refs))
        proposed = {key for key, item in FRACTIONS['concepts'].items()
                    if key in update['concepts'] or item['label'] in update['concepts']}
        if not supported or not proposed or not proposed <= supported:
            continue
        student = result[update['student_id']]
        old_misconceptions = set(student.get('misconceptions') or [])
        new_misconceptions = set(update['misconceptions'])
        removed = old_misconceptions - new_misconceptions
        catalog_misconceptions = {item['misconception']: key for key, item in FRACTIONS['concepts'].items()}
        if any(value not in catalog_misconceptions or catalog_misconceptions[value] not in supported
               for value in removed):
            continue
        # A model cannot introduce an unlisted misconception through a state update.
        if any(value not in catalog_misconceptions
               for value in new_misconceptions - old_misconceptions):
            continue
        concept_states = dict(student.get('concept_states') or {})
        for key in proposed:
            misconception = FRACTIONS['concepts'][key]['misconception']
            concept_states[key] = ('misconception' if misconception in new_misconceptions else
                                   'addressed' if concept_states.get(key) == 'misconception' else 'exposed')
        result[update['student_id']].update(understanding=update['understanding'][:500],
            concepts=[FRACTIONS['concepts'][key]['label'] for key in FRACTIONS['concepts'] if key in proposed],
            misconceptions=update['misconceptions'], concept_states=concept_states,
            correction_event_ids=list(dict.fromkeys(refs)))
    return result
