// Camera-plane geometry only. No identities, emotions, gaze targets, or teaching scores.
export const GESTURE_LABELS = {
  Open_Palm: '手掌展开', Pointing_Up: '食指向上', Closed_Fist: '握拳',
  Thumb_Up: '拇指向上', Thumb_Down: '拇指向下', Victory: 'V形手势', ILoveYou: '特定三指手形',
};
const finite = (v, low, high) => typeof v === 'number' && Number.isFinite(v) && v >= low && v <= high;
const point = (p) => p && finite(p.x, 0, 1) && finite(p.y, 0, 1);
const visible = (p) => point(p) && finite(p.visibility, .6, 1);
const rounded = (v) => Math.round(v * 1000) / 1000;

export function bodyFeatures(poses = [], aspect = 4 / 3) {
  if (poses.length > 1) return {status: 'multiple'};
  const p = poses[0];
  if (!p) return {status: 'no_detection'};
  if (![11, 12].every(i => visible(p[i]))) return {status: 'low_confidence'};
  const full = [23, 24].every(i => visible(p[i]));
  const sx = (p[11].x + p[12].x) / 2, sy = (p[11].y + p[12].y) / 2;
  const hx = full ? (p[23].x + p[24].x) / 2 : null, hy = full ? (p[23].y + p[24].y) / 2 : null;
  const lean = full && hy - sy > .05 ? Math.atan2((sx - hx) * aspect, hy - sy) * 180 / Math.PI : null;
  return {status: 'observed', scope: full ? 'torso' : 'upper_body',
    confidence: Math.min(...(full ? [11,12,23,24] : [11,12]).map(i=>p[i].visibility)),
    lean_degrees: lean === null ? null : rounded(lean), center_x: rounded(full ? (sx + hx) / 2 : sx),
    left_raised: visible(p[15]) ? p[15].y < p[11].y : null,
    right_raised: visible(p[16]) ? p[16].y < p[12].y : null};
}

export function handFeatures(result = {}) {
  const count = Math.min(2, result.landmarks?.length || 0);
  const gestures = (result.gestures || []).slice(0, count).map(categories => categories?.[0])
    .filter(g => g && Object.hasOwn(GESTURE_LABELS, g.categoryName) && finite(g.score, .7, 1))
    .map(g => ({label: g.categoryName, score: rounded(g.score)}));
  return {status: count ? 'observed' : 'no_detection', count, gestures};
}

export function faceFeatures(result = {}, aspect = 4 / 3) {
  const faces = result.faceLandmarks || [];
  if (faces.length > 1) return {status: 'multiple'};
  const p = faces[0];
  if (!p) return {status: 'no_detection'};
  if (![1, 33, 263, 61, 291].every(i => point(p[i]))) return {status: 'low_confidence'};
  const [a, b] = [p[33], p[263]].sort((a,b)=>a.x-b.x);
  const dx = (b.x-a.x)*aspect, dy = b.y-a.y, length = Math.hypot(dx,dy);
  if (length < .04) return {status: 'low_confidence'};
  const nx = (p[1].x - (a.x+b.x)/2)*aspect, ny = p[1].y - (a.y+b.y)/2;
  const offset = (nx*dx + ny*dy)/(length*length);
  if (!finite(offset,-2,2)) return {status: 'low_confidence'};
  const jaw = result.faceBlendshapes?.[0]?.categories?.find(c=>c.categoryName==='jawOpen')?.score;
  return {status: 'observed', nose_offset_ratio: rounded(offset), head_tilt_degrees: rounded(Math.atan2(dy,dx)*180/Math.PI),
    mouth_open: finite(jaw,0,1) ? rounded(jaw) : null};
}

export function motionLabels(data) {
  if (!data || data.motion_version !== 2) return [];
  const labels = [];
  if (data.body?.status === 'observed') labels.push(data.body.scope === 'upper_body' ? '上半身可见' : '肩髋可见');
  if (data.body?.left_raised || data.body?.right_raised) labels.push('抬手线索');
  for (const gesture of data.hands?.gestures || []) if (GESTURE_LABELS[gesture.label]) labels.push(GESTURE_LABELS[gesture.label]);
  if (data.face?.status === 'observed') labels.push(Math.abs(data.face.nose_offset_ratio) <= .25 ? '面部大致朝向镜头' : '面部朝向有偏移');
  if (['body','face'].some(k=>data[k]?.status==='multiple')) return ['多人入镜，暂不归属教师动作'];
  return [...new Set(labels)];
}
