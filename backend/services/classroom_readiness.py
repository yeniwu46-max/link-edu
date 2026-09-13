"""Versioned minimum evidence policy, not a calibrated teaching-quality scale.

Local scene readiness means a single teacher's upper body is observable. It does
not assert recognition of the classroom background, identity, or mental state.
"""
import math
import re
from services.classroom_motion import sanitize_motion

MIN_CLASS_SECONDS = 10
POLICY_VERSION = 'classroom-readiness-2'


def report_readiness(events, elapsed, cloud_vision=False, active_elapsed=None):
    duration = max(0, elapsed) if type(elapsed) in (int, float) and math.isfinite(elapsed) else 0
    # Ignore out-of-session timestamps and duplicate persisted event IDs.
    valid = {e['id']: e for e in events if type(e.get('id')) is int and
             type(e.get('at_ms')) is int and 0 <= e['at_ms'] <= duration * 1000 and isinstance(e.get('data'), dict)}
    rows = list(valid.values())
    if active_elapsed is not None:
        duration = max(0, active_elapsed)
    def text_length(value):
        return len(re.findall(r'[\w]', value, re.UNICODE)) if isinstance(value, str) else 0
    texts = {e['data'].get('text', '').strip() for e in rows if e.get('type') == 'transcript'
             and isinstance(e['data'].get('text'), str) and text_length(e['data']['text']) >= 5}
    chars = sum(text_length(t) for t in texts)
    completed = {e['data'].get('reply_id') for e in rows if e.get('type') == 'playback'
                 and e['data'].get('status') == 'playback_completed' and isinstance(e['data'].get('reply_id'), str)}
    incomplete = {e['data'].get('reply_id') for e in rows if
                  (e.get('type') == 'interrupt' or (e.get('type') == 'playback' and e['data'].get('status') == 'playback_failed'))
                  and isinstance(e['data'].get('reply_id'), str)}
    replies = {e['data'].get('reply_id') for e in rows if e.get('type') == 'student'
               and isinstance(e['data'].get('reply_id'), str)
               and e['data']['reply_id'] in completed - incomplete - {''} and text_length(e['data'].get('text')) >= 10}
    motion, teacher = [], []
    for e in rows:
        if e.get('type') != 'pose': continue
        data = sanitize_motion(e['data'])
        if data.get('motion_version') != 2: continue
        if any(data[k]['status'] == 'observed' for k in ('body', 'hands', 'face')): motion.append(e['at_ms'])
        if data['body']['status'] == 'observed': teacher.append(e['at_ms'])
    def sample_info(samples):
        return {'count': len(set(samples)), 'span_seconds': round((max(samples) - min(samples)) / 1000, 2) if samples else 0}
    motion_info, teacher_info = sample_info(motion), sample_info(teacher)
    enough_samples = lambda info: info['count'] >= 3 and info['span_seconds'] >= 4
    vision = [e for e in rows if e.get('type') == 'vision' and
              e['data'].get('scene_detected') is True and
              type(e['data'].get('confidence')) in (int, float) and .6 <= e['data']['confidence'] <= 1
              and text_length(e['data'].get('observations')) >= 10]
    checks = []
    def add(key, label, passed, actual, minimum, reason):
        checks.append(dict(key=key, label=label, passed=bool(passed), actual=actual, minimum=minimum, reason='' if passed else reason))
    add('duration', '授课时长', duration >= MIN_CLASS_SECONDS, round(duration, 1), MIN_CLASS_SECONDS,
        f'授课未满 {MIN_CLASS_SECONDS} 秒（当前 {duration:.1f} 秒）。')
    add('transcript', '最终语音转写', len(texts) >= 2 and chars >= 80, {'segments': len(texts), 'characters': chars},
        {'segments': 2, 'characters': 80}, f'最终转写不足：当前 {len(texts)} 段、{chars} 字；需至少 2 段、80 字（不含标点）。')
    add('interaction', '学生反馈', len(replies) >= 1, len(replies), 1,
        '学生反馈不足：需至少 1 次不少于 10 字且确认完整播放的回应；生成、打断或播放失败不计入。')
    add('motion', '动作姿态采样', enough_samples(motion_info), motion_info, {'count': 3, 'span_seconds': 4},
        f"动作捕捉不足：{motion_info['count']} 个有效样本，跨度 {motion_info['span_seconds']} 秒；需至少 3 个、跨度 4 秒。")
    local_scene = enough_samples(teacher_info)
    scene_ok = local_scene and (not cloud_vision or bool(vision))
    scene_reason = ('未识别到足够的单人教师画面：请让上半身清晰入镜，至少 3 个有效样本、跨度 4 秒。' if not local_scene else '')
    if cloud_vision and not vision:
        scene_reason += ' 已开启云端画面分析，但未识别到有效授课场景（至少 1 条、置信度 ≥ 0.6）。'
    add('scene', '教师画面 / 场景证据', scene_ok, {'teacher': teacher_info, 'cloud_observations': len(vision)},
        {'teacher_samples': 3, 'span_seconds': 4, 'cloud_observations': 1 if cloud_vision else 0}, scene_reason.strip())
    for check in checks:
        check['scope'] = 'posture' if check['key'] in ('motion', 'scene') else 'report'
    return {'version': POLICY_VERSION, 'eligible': all(c['passed'] for c in checks if c['scope'] == 'report'), 'checks': checks,
            'dimension_eligibility': {'posture': enough_samples(motion_info) and scene_ok},
            'reasons': [c['reason'] for c in checks if not c['passed']],
            'scene_mode': 'local_teacher_frame_and_cloud' if cloud_vision else 'local_teacher_frame',
            'notice': '仅为最低数据完整性检查，不代表教学质量达标；本地入镜检测不等于课堂背景语义识别。'}
