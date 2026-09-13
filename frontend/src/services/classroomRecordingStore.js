export const MAX_RECORDING_BYTES = 250 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 1024 * 1024 * 1024;
const STORE = 'recordings';
export function recordingKey(origin, userId, sessionId) {
  if (!origin || !Number.isSafeInteger(Number(userId)) || Number(userId) <= 0 ||
      !Number.isSafeInteger(Number(sessionId)) || Number(sessionId) <= 0) throw new Error('缺少有效用户或课堂编号');
  return JSON.stringify([origin, Number(userId), Number(sessionId)]);
}
export function recordingTime(segments, at) {
  if (!Number.isFinite(at)) return null;
  const segment = (segments || []).find(s => at >= s.wallStart && at < s.wallEnd);
  return segment ? (segment.videoStart + at - segment.wallStart) / 1000 : null;
}
export function canStore(items, key, bytes) {
  return bytes > 0 && bytes <= MAX_RECORDING_BYTES &&
    items.filter(r => r.key !== key).reduce((n,r) => n + r.byteLength, bytes) <= MAX_TOTAL_BYTES;
}
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('link-classroom-recordings', 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, {keyPath:'key'});
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(new Error('浏览器本机存储不可用，可下载视频'));
  });
}
async function transact(mode, work) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    let result, error;
    tx.oncomplete = () => {db.close(); resolve(result);};
    tx.onabort = tx.onerror = () => {db.close(); reject(error || tx.error || new Error('本机保存失败，可下载视频'));};
    work(tx.objectStore(STORE), value => {result=value;}, message => {error=new Error(message); tx.abort();});
  });
}
export function saveClassroomRecording(origin, userId, sessionId, blob, meta) {
  const key = recordingKey(origin, userId, sessionId);
  // Vue reactive objects are not structured-cloneable. Persist a bounded plain DTO.
  const metadata = {filename:String(meta.filename || `LINK-课堂-${sessionId}.webm`),
    durationMs:Number(meta.durationMs)||0,segments:(meta.segments || []).map(s=>({
      wallStart:Number(s.wallStart),wallEnd:Number(s.wallEnd),videoStart:Number(s.videoStart)}))};
  return transact('readwrite', (store, done, fail) => {
    const req = store.getAll();
    req.onsuccess = () => {
      if (!canStore(req.result, key, blob.size)) return fail('本机录像容量不足，请下载或手动删除旧录像；未删除任何记录。');
      const row = {...metadata, key, origin, userId:Number(userId), sessionId:Number(sessionId),
        blob, byteLength:blob.size, savedAt:Date.now(), mimeType:blob.type};
      try {store.put(row); done(row);} catch {fail('录像保存失败，可下载视频；未修改已有录像。');}
    };
  });
}
export function getClassroomRecording(origin, userId, sessionId) {
  const key = recordingKey(origin, userId, sessionId);
  return transact('readonly', (store, done) => {const req=store.get(key); req.onsuccess=()=>done(req.result || null);});
}
export function listClassroomRecordings(origin, userId) {
  recordingKey(origin, userId, 1);
  return transact('readonly', (store, done) => {
    const req=store.getAll(); req.onsuccess=()=>done(req.result.filter(r=>r.origin===origin && r.userId===Number(userId))
      .map(({blob,...meta})=>meta).sort((a,b)=>b.savedAt-a.savedAt));
  });
}
export function deleteClassroomRecording(origin, userId, sessionId) {
  const key=recordingKey(origin,userId,sessionId);
  return transact('readwrite',(store,done)=>{store.delete(key);done(true);});
}
