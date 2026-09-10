export function resolveResourceLink(value, origin) {
  const raw = String(value || '').trim()
  if (!raw) return { status: 'missing', url: '', external: false }
  try {
    const url = new URL(raw, origin)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Invalid resource URL')
    return { status: 'ready', url: url.href, external: url.origin !== origin }
  } catch {
    return { status: 'invalid', url: '', external: false }
  }
}
