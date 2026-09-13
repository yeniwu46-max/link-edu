const MIME_CANDIDATES = [
  'video/webm;codecs=vp9',
  'video/webm;codecs=vp8',
  'video/webm',
  'video/mp4',
]

const MAX_FRAMES = 8
const FRAME_INTERVAL_MS = 50_000

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return ''
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) || ''
}

function stampName(label = '训练') {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const day = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}`
  const safe = String(label || '训练').replace(/[\\/:*?"<>|]+/g, '').trim() || '训练'
  return `临客训练-${safe}-${day}-${time}`
}

function extensionFor(mime) {
  if (String(mime || '').includes('mp4')) return 'mp4'
  return 'webm'
}

export function captureVideoFrame(videoEl, quality = 0.72) {
  if (!videoEl || videoEl.readyState < 2 || !videoEl.videoWidth) return ''
  const canvas = document.createElement('canvas')
  const width = Math.min(640, videoEl.videoWidth)
  const height = Math.round((videoEl.videoHeight / videoEl.videoWidth) * width)
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''
  ctx.drawImage(videoEl, 0, 0, width, height)
  try {
    return canvas.toDataURL('image/jpeg', quality)
  } catch {
    return ''
  }
}

export function createTrainingRecorder() {
  let recorder = null
  let chunks = []
  let objectUrl = ''
  let mimeType = ''
  let recording = false
  let frames = []
  let frameTimer = 0
  let videoEl = null

  function supported() {
    return Boolean(pickMimeType())
  }

  function isRecording() {
    return recording
  }

  function frameCount() {
    return frames.length
  }

  function getFrames() {
    return frames.slice()
  }

  function pushFrame() {
    if (frames.length >= MAX_FRAMES || !videoEl) return
    const dataUrl = captureVideoFrame(videoEl)
    if (!dataUrl || !dataUrl.startsWith('data:image/jpeg')) return
    if (dataUrl.length > 400_000) return
    frames.push(dataUrl)
  }

  function startFrameCapture(el) {
    videoEl = el || null
    frames = []
    if (frameTimer) window.clearInterval(frameTimer)
    pushFrame()
    frameTimer = window.setInterval(() => {
      pushFrame()
      if (frames.length >= MAX_FRAMES && frameTimer) {
        window.clearInterval(frameTimer)
        frameTimer = 0
      }
    }, FRAME_INTERVAL_MS)
  }

  function stopFrameCapture() {
    pushFrame()
    if (frameTimer) {
      window.clearInterval(frameTimer)
      frameTimer = 0
    }
    videoEl = null
  }

  function start(stream, options = {}) {
    dispose({ keepFrames: false })
    mimeType = pickMimeType()
    if (!mimeType) {
      throw new Error('当前浏览器不支持本机录像')
    }
    if (!stream || !stream.getVideoTracks?.().some((track) => track.readyState === 'live')) {
      throw new Error('没有可用的镜头画面，无法开始录制')
    }

    chunks = []
    recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 2_500_000,
    })
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunks.push(event.data)
    }
    recorder.start(1000)
    recording = true
    if (options.videoEl) startFrameCapture(options.videoEl)
  }

  function stop(label = '训练') {
    stopFrameCapture()
    return new Promise((resolve) => {
      if (!recorder || recorder.state === 'inactive') {
        recording = false
        resolve(null)
        return
      }

      const active = recorder
      active.onstop = () => {
        recording = false
        recorder = null
        if (!chunks.length) {
          resolve(null)
          return
        }
        const blob = new Blob(chunks, { type: mimeType || 'video/webm' })
        chunks = []
        if (objectUrl) URL.revokeObjectURL(objectUrl)
        objectUrl = URL.createObjectURL(blob)
        const filename = `${stampName(label)}.${extensionFor(mimeType)}`
        resolve({
          blob,
          url: objectUrl,
          filename,
          mimeType,
          frames: frames.slice(),
        })
      }
      try {
        if (active.state === 'recording') active.requestData()
        active.stop()
      } catch {
        recording = false
        recorder = null
        resolve(null)
      }
    })
  }

  function download(result) {
    if (!result?.blob && !result?.url) return
    const url = result.url || URL.createObjectURL(result.blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = result.filename || `${stampName()}.webm`
    anchor.rel = 'noopener'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    if (!result.url) URL.revokeObjectURL(url)
  }

  function dispose({ keepFrames = false } = {}) {
    stopFrameCapture()
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.onstop = null
        recorder.stop()
      } catch {
        /* already stopped */
      }
    }
    recorder = null
    chunks = []
    recording = false
    if (!keepFrames) frames = []
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = ''
    }
  }

  return {
    supported,
    isRecording,
    frameCount,
    getFrames,
    start,
    stop,
    download,
    dispose,
  }
}
