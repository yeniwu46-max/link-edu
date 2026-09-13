"""Observable motion evidence, not an emotion detector or an automatic teaching score."""
import math

VERSION = 'motion-rubric-1'
STATUSES = {'observed', 'no_detection', 'low_confidence', 'multiple', 'failed', 'loading', 'disabled'}
GESTURES = {'Open_Palm', 'Pointing_Up', 'Closed_Fist', 'Thumb_Up', 'Thumb_Down', 'Victory', 'ILoveYou'}


def number(value, low, high):
    return value if type(value) in (int, float) and math.isfinite(value) and low <= value <= high else None


def boolean(value):
    return value if type(value) is bool else None


def sanitize_motion(data):
    if not isinstance(data, dict):
        raise ValueError('动作数据格式错误')
    clean = {k: boolean(data.get(k)) for k in ('present', 'left_raised', 'right_raised')}
    for key, low, high in (('confidence', 0, 1), ('lean_degrees', -180, 180), ('center_x', -2, 3), ('movement', 0, 5)):
        clean[key] = number(data.get(key), low, high)
    if type(data.get('motion_version')) is not int or data['motion_version'] != 2:
        return clean
    clean.update(motion_version=2, source='mediapipe-local')
    for name in ('body', 'hands', 'face'):
        raw = data.get(name) if isinstance(data.get(name), dict) else {}
        status = raw.get('status') if isinstance(raw.get('status'), str) and raw['status'] in STATUSES else 'low_confidence'
        item = {'status': status}
        if status == 'observed' and name == 'body':
            item.update(confidence=number(raw.get('confidence'), .6, 1),
                        scope=raw.get('scope') if raw.get('scope') in ('upper_body', 'torso') else None,
                        lean_degrees=number(raw.get('lean_degrees'), -90, 90),
                        center_x=number(raw.get('center_x'), 0, 1),
                        left_raised=boolean(raw.get('left_raised')), right_raised=boolean(raw.get('right_raised')))
            if item['scope'] == 'upper_body':
                item['lean_degrees'] = None
            if item['confidence'] is None or item['scope'] is None:
                item = {'status': 'low_confidence'}
        elif status == 'observed' and name == 'hands':
            count = raw.get('count')
            item['count'] = count if type(count) is int and 1 <= count <= 2 else 0
            gestures = raw.get('gestures') if isinstance(raw.get('gestures'), list) else []
            item['gestures'] = [{'label': g['label'], 'score': g['score']} for g in gestures[:2]
                                if isinstance(g, dict) and isinstance(g.get('label'), str) and g['label'] in GESTURES and
                                number(g.get('score'), .7, 1) is not None][:item['count']]
            if not item['count']:
                item = {'status': 'no_detection'}
        elif status == 'observed' and name == 'face':
            for key, low, high in (('nose_offset_ratio', -2, 2), ('head_tilt_degrees', -90, 90), ('mouth_open', 0, 1)):
                item[key] = number(raw.get(key), low, high)
            if item['nose_offset_ratio'] is None or item['head_tilt_degrees'] is None:
                item = {'status': 'low_confidence'}
        clean[name] = item
    # Without identity tracking, multiple people cannot be attributed to this teacher.
    if any(clean[k]['status'] == 'multiple' for k in ('body', 'face')):
        for k in ('body', 'hands', 'face'):
            clean[k] = {'status': 'multiple'}
    return clean


def representatives(events):
    return list(dict.fromkeys(e['id'] for e in (events[:3] + events[-5:])))


def motion_evidence(events):
    frames = sorted([dict(e, data=sanitize_motion(e['data'])) for e in events
                     if e.get('type') == 'pose' and isinstance(e.get('data'), dict) and
                     type(e['data'].get('motion_version')) is int and e['data']['motion_version'] == 2],
                    key=lambda e: e.get('at_ms', 0))
    observed = {name: [e for e in frames if e['data'][name]['status'] == 'observed'] for name in ('body', 'hands', 'face')}
    valid = [e for e in frames if any(e['data'][k]['status'] == 'observed' for k in observed)]
    sufficient = len(valid) >= 3 and valid[-1].get('at_ms', 0) - valid[0].get('at_ms', 0) >= 4000
    result = {'version': VERSION, 'status': 'observed' if sufficient else 'insufficient',
              'sample_count': len(frames), 'observed_samples': len(valid), 'modalities': {}, 'observations': [],
              'eligible_event_ids': [], 'limitations': [
                  '约2秒抽样一次；样本比例不是整堂课时长占比，不能保证捕获瞬时动作。',
                  '仅为单人摄像头几何线索，无法确认目光对象、手势意图或心理状态。',
                  '坐姿、个体活动方式及板书情境均应结合上下文，不要求固定站姿或微笑。']}
    for name, samples in observed.items():
        result['modalities'][name] = {'observed_samples': len(samples), 'total_samples': len(frames),
                                     'status_counts': {s: sum(e['data'][name]['status'] == s for e in frames) for s in sorted(STATUSES)},
                                     'event_ids': representatives(samples)}
    def add(code, modality, predicate, description, suggestion, applicable=lambda item: True):
        samples = [e for e in observed[modality] if applicable(e['data'][modality])]
        matched = [e for e in samples if predicate(e['data'][modality])]
        if not matched:
            return
        matching = {e['id'] for e in matched}
        longest, start, previous = 0, None, None
        for e in frames:
            at = e.get('at_ms', 0)
            if e['id'] not in matching:
                start = previous = None
                continue
            if previous is None or at - previous > 4000:
                start = at
            longest = max(longest, at - start)
            previous = at
        result['observations'].append({'code': code, 'modality': modality, 'description': description,
            'suggestion': suggestion, 'matched_samples': len(matched), 'observed_samples': len(samples),
            'sample_ratio': round(len(matched) / len(samples), 3), 'event_ids': representatives(matched),
            'first_at_ms': matched[0].get('at_ms', 0), 'last_at_ms': matched[-1].get('at_ms', 0),
            'longest_observed_span_ms': longest})
    add('body_upright', 'body', lambda b: b['lean_degrees'] is not None and abs(b['lean_degrees']) <= 15,
        '画面内躯干接近竖直', '只描述画面几何；不能据此认定教学优秀或要求教师始终站立。',
        applicable=lambda b: b['lean_degrees'] is not None)
    add('body_lateral_lean', 'body', lambda b: b['lean_degrees'] is not None and abs(b['lean_degrees']) > 20,
        '画面内躯干有侧倾线索', '连续多个样本出现时，结合板书/示范情境和个人活动方式再讨论是否需要调整机位或体态。',
        applicable=lambda b: b['lean_degrees'] is not None)
    add('arm_raised', 'body', lambda b: b['left_raised'] is True or b['right_raised'] is True,
        '手腕高于同侧肩部', '结合授课转写判断是否用于指示或互动；抬手本身不加分。',
        applicable=lambda b: b['left_raised'] is not None or b['right_raised'] is not None)
    gesture_advice = {
        'Open_Palm': '若处于概念解释或操作演示环节，可核对展开手掌是否帮助呈现内容，并建议示范部位保持入镜。',
        'Pointing_Up': '若用于强调重点，可核对手势与当前问题是否一致；不能从食指手形确定其实际指向的对象。',
        'Thumb_Up': '若出现在学生回应后，可结合教师反馈语评价反馈是否具体；不能单凭手势认定鼓励有效。',
        'Thumb_Down': '若处于纠错环节，可结合措辞建议说明错因与改进方向；不能单凭手形认定否定学生。',
    }
    for label, text in [('Open_Palm', '手掌展开'), ('Pointing_Up', '食指向上'), ('Closed_Fist', '握拳'),
                        ('Thumb_Up', '拇指向上'), ('Thumb_Down', '拇指向下'), ('Victory', 'V形手势'), ('ILoveYou', '特定三指手形')]:
        code = 'hand_' + {'Open_Palm': 'open_palm'}.get(label, label.lower())
        add(code, 'hands', lambda h, label=label: any(g['label'] == label for g in h['gestures']), text,
            gesture_advice.get(label, '结合对应时间点的讲解，核对是否清晰辅助指示、示范或反馈。') +
            '手形识别不等于意图，不按手势数量机械评分。')
    add('head_camera_aligned', 'face', lambda f: abs(f['nose_offset_ratio']) <= .25,
        '面部几何大致朝向镜头', '镜头方向不等于学生方向，不能据此声称与学生有目光交流。')
    add('head_off_camera', 'face', lambda f: abs(f['nose_offset_ratio']) > .35,
        '面部朝向偏离镜头的几何线索', '结合板书、阅读或演示情境；不能直接认定背对学生或缺少互动。')
    add('head_tilt', 'face', lambda f: abs(f['head_tilt_degrees']) > 20,
        '头部在画面内倾斜', '仅作几何观察，不推断疲倦、自信、态度或人格。')
    add('mouth_open', 'face', lambda f: f['mouth_open'] is not None and f['mouth_open'] >= .5,
        '口部张开形变线索', '不能单凭口部动作认定发音清晰、情绪或讲话时长，需结合实际音频转写。',
        applicable=lambda f: f['mouth_open'] is not None)
    if sufficient:
        result['eligible_event_ids'] = sorted({e['id'] for e in valid})
    completed = {e['data'].get('reply_id') for e in events if e.get('type') == 'playback'
                 and e.get('data', {}).get('status') == 'playback_completed'}
    completed -= {e.get('data', {}).get('reply_id') for e in events if e.get('type') == 'interrupt'
                  or (e.get('type') == 'playback' and e.get('data', {}).get('status') == 'playback_failed')}
    replies = {e['data'].get('reply_id'): e for e in events if e.get('type') == 'student'}
    context = [e for e in events if e.get('type') == 'transcript']
    for e in events:
        rid = e.get('data', {}).get('reply_id')
        if e.get('type') == 'playback' and rid in completed and rid in replies and type(e.get('at_ms')) is int:
            context.append(dict(replies[rid], at_ms=e['at_ms'], playback_event_id=e['id']))
    by_id = {e['id']: e for e in frames}
    for observation in result['observations']:
        nearby = [e for e in context if type(e.get('at_ms')) is int and any(abs(e['at_ms'] - by_id[i]['at_ms']) <= 5000
                                             for i in observation['event_ids'])]
        observation['context'] = [{'event_id': e['id'], 'at_ms': e['at_ms'],
            'text': str(e['data'].get('text', ''))[:300], 'playback_event_id': e.get('playback_event_id')}
            for e in nearby[:8]]
        observation['context_notice'] = '前后5秒候选关联，不证明手势意图或指向对象。'
    result['version'] = 'motion-rubric-2'
    return result
