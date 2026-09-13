"""Versioned simulated knowledge; never a score or proof of learning."""
from copy import deepcopy
import re

IDS = ('ming', 'yu', 'lin')
NAMES = {'小明': 'ming', '小雨': 'yu', '小林': 'lin'}
INTENTS = {'named_question', 'class_question', 'invite', 'resume', 'rhetorical', 'self_talk', 'lecture', 'address'}


def normalize_states(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for sid in IDS:
        old = raw.get(sid) if isinstance(raw.get(sid), dict) else {}
        result[sid] = dict(version=2, understanding=old.get('understanding', ''),
            concepts=old.get('concepts', []), misconceptions=old.get('misconceptions',
                ['可能混淆平均分与分母大小'] if sid == 'yu' and not old else []),
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
    elif re.search(r'难道|岂不是|何尝|不是.*(?:吗|么)', text):
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
        result[update['student_id']].update(understanding=update['understanding'][:500],
            concepts=update['concepts'], misconceptions=update['misconceptions'], correction_event_ids=list(dict.fromkeys(refs)))
    return result
