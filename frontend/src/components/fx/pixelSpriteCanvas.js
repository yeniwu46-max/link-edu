import { frameRect } from '../../services/pixelCharacters.js'

export async function loadPixelAtlas(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error('Pixel character unavailable')
  const bitmap = await createImageBitmap(await response.blob())
  if (signal?.aborted) { bitmap.close(); throw new DOMException('Aborted', 'AbortError') }
  return bitmap
}

export function drawPixelSprite(ctx, image, frame, rect, close = false, facing = 0) {
  const source = frameRect(image, frame)
  const size = Math.min(rect.width, rect.height) * (close ? 1.3 : .94)
  const x = Math.round(rect.x + (rect.width - size) / 2)
  const y = Math.round(rect.y + (rect.height - size) / 2 + (close ? size * .09 : 0))
  ctx.save()
  ctx.beginPath(); ctx.rect(rect.x, rect.y, rect.width, rect.height); ctx.clip()
  ctx.imageSmoothingEnabled = false
  if (frame === 11 && facing > 0) { ctx.translate(x * 2 + size, 0); ctx.scale(-1, 1) }
  ctx.drawImage(image, source.x, source.y, source.width, source.height, x, y, size, size)
  ctx.restore()
}
