"""Versioned rehearsal scenarios; these are simulated roles, not learner measurements."""

import re


FRACTIONS = {
    'id': 'primary-math-fractions',
    'version': 1,
    'topic': '分数的初步认识',
    'grade': '小学三年级',
    'objective': '解释平均分、几分之一和同一整体，并回应学生的典型误解。',
    'concepts': {
        'equal_parts': {'label': '平均分', 'misconception': '不等分也可以表示二分之一'},
        'unit_fraction': {'label': '几分之一', 'misconception': '分母越大，每份一定越大'},
        'same_whole': {'label': '同一整体', 'misconception': '不同整体的分数份量可以直接比较'},
    },
    'students': {
        'ming': {'focus': '追问为什么，但不提前知道未讲内容', 'initial_misconceptions': []},
        'yu': {'focus': '容易把不等分误认为二分之一', 'initial_misconceptions': ['equal_parts']},
        'lin': {'focus': '较少主动发言，仅点名后回应', 'initial_misconceptions': []},
    },
}


def supported_concepts(text):
    """Conservative evidence gate for concept exposure in the fractions scenario."""
    value = re.sub(r'\s+', '', str(text or ''))
    found = set()
    wrong_equal_parts = re.search(r'平均分.{0,8}(不是|不用|不需要).{0,8}(每.{0,3}份|相等)|每.{0,3}份.{0,6}(不一样|不相同|不相等).{0,12}平均分', value)
    if not wrong_equal_parts and (('平均分' in value and re.search(r'每.{0,3}份.{0,8}(一样|同样|相同|相等)', value)) or re.search(
            r'每.{0,3}份.{0,8}(一样|同样|相同|相等).{0,12}平均分', value)):
        found.add('equal_parts')
    if re.search(r'分成.{1,4}份.{0,8}(其中|拿出|取出)一份|分母越大.{0,8}每份越小', value):
        found.add('unit_fraction')
    if not re.search(r'(不需要|无需|不用).{0,8}(同一|同一个|相同).{0,4}整体', value) and re.search(r'(同一|同一个|相同|一样大).{0,4}整体', value) and re.search(
            r'(比较|大小|分数|份)', value):
        found.add('same_whole')
    return found


def scenario_brief():
    return {key: FRACTIONS[key] for key in ('id', 'version', 'topic', 'grade', 'objective', 'concepts', 'students')}
