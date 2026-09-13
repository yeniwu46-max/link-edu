export const CALIBRATION_LABELS = {observed:'可观察', no_detection:'未检测到', low_confidence:'遮挡或质量不足',
  multiple:'画面有多人', failed:'检测不可用', loading:'模型加载中', disabled:'未开启'};
export function calibrationSummary(samples) {
  return Object.fromEntries(['body','hands','face'].map(key => {
    const observed=samples.filter(s=>s?.[key]?.status==='observed').length;
    const latest=samples.at(-1)?.[key]?.status || 'loading';
    return [key,{observed,total:samples.length,status:observed ? 'observed' : latest}];
  }));
}
