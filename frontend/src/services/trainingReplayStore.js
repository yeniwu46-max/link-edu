const DB_NAME = 'link-training-replay'
const STORE = 'recordings'
const DB_VERSION = 1
const MAX_ITEMS = 10

function openDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'sessionId' })
        store.createIndex('savedAt', 'savedAt')
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('IndexedDB open failed'))
  })
}

export async function putRecording(sessionId, blob, meta = {}) {
  const id = Number(sessionId)
  if (!id || !blob) throw new Error('缺少 sessionId 或录像数据')
  const record = {
    sessionId: id,
    blob,
    mimeType: blob.type || meta.mimeType || 'video/webm',
    filename: meta.filename || `临客训练-${id}.webm`,
    courseTitle: meta.courseTitle || '',
    savedAt: Date.now(),
    byteLength: blob.size || 0,
  }
  const db = await openDb()
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const store = tx.objectStore(STORE)
    store.put(record)
    const allReq = store.getAll()
    allReq.onsuccess = () => {
      const items = allReq.result || []
      if (items.length <= MAX_ITEMS) return
      items
        .sort((a, b) => Number(a.savedAt || 0) - Number(b.savedAt || 0))
        .slice(0, items.length - MAX_ITEMS)
        .forEach((item) => store.delete(item.sessionId))
    }
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => {
      db.close()
      reject(tx.error || new Error('保存录像失败'))
    }
  })
  return record
}

export async function getRecording(sessionId) {
  const id = Number(sessionId)
  if (!id) return null
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const request = tx.objectStore(STORE).get(id)
    request.onsuccess = () => {
      db.close()
      resolve(request.result || null)
    }
    request.onerror = () => {
      db.close()
      reject(request.error || new Error('读取录像失败'))
    }
  })
}

export async function deleteRecording(sessionId) {
  const id = Number(sessionId)
  if (!id) return
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).delete(id)
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => {
      db.close()
      reject(tx.error || new Error('删除录像失败'))
    }
  })
}
