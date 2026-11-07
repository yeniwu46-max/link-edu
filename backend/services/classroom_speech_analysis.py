"""Explainable, low-stakes tags for live teacher speech evidence."""
import re


RULES = (
    ('question', ('吗', '呢？', '？', '?', '怎么', '为什么', '哪一个', '谁来', '有没有', '是不是')),
    ('invite', ('请你', '请一位', '谁愿意', '谁来', '你来', '同学们说', '请说', '请回答', '举手')),
    ('reasoning_probe', ('为什么', '理由', '解释一下', '说说你的想法', '怎么想到', '依据是什么', '凭什么')),
    ('explanation', ('也就是', '因为', '所以', '我们可以', '注意看', '举个例子', '换句话说', '先看')),
    ('feedback', ('很好', '说得对', '正确', '不对', '再想想', '我补充', '你刚才', '回答得', '谢谢你')),
    ('recap', ('总结一下', '回顾一下', '今天我们', '这节课', '最后记住', '归纳一下')),
)


LABELS = {
    'question': '提出问题', 'invite': '邀请参与', 'reasoning_probe': '追问理由',
    'explanation': '解释 / 示范', 'feedback': '反馈 / 承接', 'recap': '总结 / 回顾',
}


def classify_teaching_utterance(text):
    """Return transparent rule hits; these are candidate discourse acts, not a validated rubric."""
    text = re.sub(r'\s+', '', str(text or ''))[:4000]
    hits = []
    for key, cues in RULES:
        matched = [cue for cue in cues if cue in text]
        if matched:
            hits.append({'key': key, 'label': LABELS[key], 'cues': matched[:3]})
    return {
        'version': 1,
        'method': 'transparent_lexical_rules',
        'labels': hits,
        'notice': '自动候选标签，按原话词语匹配；不等同 CLASS 编码或已验证的教学行为分类。请结合上下文复核。',
    }


def aggregate_voice_features(items):
    """Aggregate client-side acoustic descriptors. Never infer emotion from these values."""
    usable = [x for x in items if isinstance(x, dict) and x.get('rms_dbfs') is not None]
    if not usable:
        return {'status': 'insufficient', 'notice': '未取得足够的本机声学采样。'}
    levels = [max(-100.0, min(0.0, float(x['rms_dbfs']))) for x in usable]
    pitches = [float(x['pitch_hz']) for x in usable if isinstance(x.get('pitch_hz'), (int, float)) and 60 <= x['pitch_hz'] <= 500]
    crossings = [float(x['zero_crossing_rate']) for x in usable if isinstance(x.get('zero_crossing_rate'), (int, float))]
    spread = max(levels) - min(levels)
    pitch_spread = max(pitches) - min(pitches) if len(pitches) >= 3 else None
    if len(usable) < 3:
        cue = '采样较少，暂不描述声音起伏'
    elif spread >= 14 or (pitch_spread is not None and pitch_spread >= 70):
        cue = '本段音量或基频变化较明显'
    elif spread <= 7 and (pitch_spread is None or pitch_spread <= 35):
        cue = '本段音量与基频变化较平稳'
    else:
        cue = '本段存在一定声音变化'
    return {
        'status': 'candidate', 'sample_count': len(usable),
        'mean_rms_dbfs': round(sum(levels) / len(levels), 1),
        'level_range_db': round(spread, 1),
        'pitch_mean_hz': round(sum(pitches) / len(pitches), 1) if pitches else None,
        'pitch_range_hz': round(pitch_spread, 1) if pitch_spread is not None else None,
        'mean_zero_crossing_rate': round(sum(crossings) / len(crossings), 3) if crossings else None,
        'cue': cue,
        'notice': '仅为音量/基频变化描述，不判断正面或负面情绪，也不推断教师内在状态；自动增益、距离和噪声会影响结果。',
    }
