// Lightweight mouse-driven glow for browsers without floating-point WebGL.
export function createLiquidEtherFallback(container) {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  if (!context) return () => {}
  canvas.style.cssText = 'display:block;width:100%;height:100%'
  container.append(canvas)
  let width = 1
  let height = 1
  let frame = 0
  let visible = true
  let particles = []
  let lastPoint
  const lifetime = 1300

  function resize() {
    const rect = container.getBoundingClientRect()
    width = Math.max(1, rect.width)
    height = Math.max(1, rect.height)
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
    canvas.width = Math.round(width * ratio)
    canvas.height = Math.round(height * ratio)
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
  }

  function draw(now) {
    frame = 0
    context.clearRect(0, 0, width, height)
    particles = particles.filter(particle => now - particle.time < lifetime)
    for (const particle of particles) {
      const age = (now - particle.time) / lifetime
      const radius = 34 + age * 65
      const x = particle.x + Math.sin(age * 5 + particle.phase) * age * 24
      const y = particle.y - age * 28
      const glow = context.createRadialGradient(x, y, 0, x, y, radius)
      glow.addColorStop(0, `rgba(240, 145, 255, ${0.24 * (1 - age)})`)
      glow.addColorStop(.4, `rgba(139, 65, 255, ${0.15 * (1 - age)})`)
      glow.addColorStop(1, 'rgba(82, 39, 255, 0)')
      context.fillStyle = glow
      context.fillRect(x - radius, y - radius, radius * 2, radius * 2)
    }
    if (particles.length && visible && !document.hidden) frame = requestAnimationFrame(draw)
  }

  function move(event) {
    if (!visible || document.hidden) return
    const rect = container.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    if (x < 0 || y < 0 || x > width || y > height) { lastPoint = undefined; return }
    const time = performance.now()
    const previous = lastPoint && time - lastPoint.time < 150 ? lastPoint : { x, y }
    const steps = Math.min(12, Math.max(1, Math.ceil(Math.hypot(x - previous.x, y - previous.y) / 12)))
    for (let i = 1; i <= steps; i++) {
      particles.push({ x: previous.x + (x - previous.x) * i / steps,
        y: previous.y + (y - previous.y) * i / steps, time, phase: time * .002 })
    }
    particles = particles.slice(-100)
    lastPoint = { x, y, time }
    if (!frame) frame = requestAnimationFrame(draw)
  }

  function stop() {
    cancelAnimationFrame(frame)
    frame = 0
    particles = []
    lastPoint = undefined
    context.clearRect(0, 0, width, height)
  }

  function visibilityChange() { if (document.hidden) stop() }
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    if (!visible) stop()
  })
  const resizeObserver = new ResizeObserver(resize)
  resize()
  observer.observe(container)
  resizeObserver.observe(container)
  window.addEventListener('mousemove', move, { passive: true })
  document.addEventListener('visibilitychange', visibilityChange)

  return () => {
    stop()
    observer.disconnect()
    resizeObserver.disconnect()
    window.removeEventListener('mousemove', move)
    document.removeEventListener('visibilitychange', visibilityChange)
    canvas.remove()
  }
}
