// Synthetic integration QA: no real classroom data, model calls, devices or external traffic.
async (page) => {
  page.setDefaultTimeout(12000)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  page.removeAllListeners('pageerror')
  const errors = [], failures = [], layouts = [], generated = []
  const check = (ok, message) => { if (!ok) failures.push(message) }
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('link_token', 'synthetic-ui-sync')
    navigator.mediaDevices.getUserMedia = async () => { throw Error('Devices blocked') }
  })
  const reports = [
    { id: 101, session_id: 11, course_title: '合成课堂甲', overall_score: 82, created_at: '2026-09-13T10:00:00Z', report: { source: 'deepseek', generation_status: 'succeeded', demo: false, summary: '合成观察甲', dimensions: [{ key: 'clarity', label: '表达清晰度', score: 82 }] } },
    { id: 102, session_id: 12, course_title: '合成课堂乙', overall_score: null, created_at: '2026-09-12T10:00:00Z', report: { source: 'deepseek', generation_status: 'succeeded', insufficient_evidence: true, demo: false, dimensions: [{ key: 'clarity', label: '表达清晰度', score: 0 }] } },
  ]
  let growthFails = false
  await page.route('**/*', async route => {
    const request = route.request(), path = request.url().replace(/^http:\/\/127\.0\.0\.1:5188/, '').split('?')[0]
    if (!request.url().startsWith('http://127.0.0.1:5188/')) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 909, name: '合成验收', role: 'student' } })
    if (path === '/api/feedbacks') return route.fulfill({ json: { items: reports } })
    if (path.endsWith('/ai-review')) {
      generated.push(request.postDataJSON())
      reports[0].report.generation_status = 'failed'
      reports[0].report.generation_error = '合成验收：模型暂不可用'
      return route.fulfill({ status: 503, json: { message: '合成验收：模型暂不可用' } })
    }
    if (path === '/api/growth') {
      if (growthFails) return route.fulfill({ status: 503, json: { message: '合成验收：成长加载失败' } })
      return route.fulfill({ json: {
        points: [{ date: '09/12', score: 78, clarity: 80, pace: 76, interaction: 78 }, { date: '09/13', score: 82, clarity: 82, pace: 83, interaction: 81 }],
        heatmap: [{ date: '2026-09-12', count: 1, minutes: 8, level: 1 }, { date: '2026-09-13', count: 1, minutes: 8, level: 1 }],
        records: reports.map(item => ({ ...item, when: item.created_at, date: item.created_at.slice(0, 10) })),
        journals: [{ id: 1, entry_date: '2026-09-13', body: '合成日志：等待学生回答' }], summaries: [], milestones: [],
      } })
    }
    return route.fulfill({ status: 404, json: { message: 'No synthetic fixture' } })
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    for (const path of ['/growth', '/ai-review?sessionId=11&feedbackId=101']) {
      await page.goto(`http://127.0.0.1:5188${path}`)
      await page.locator(path === '/growth' ? '.growth-record-list' : '.review-list').waitFor()
      const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }))
      layouts.push({ path, ...layout })
      check(layout.scroll <= width, `Overflow: ${path} at ${width}`)
      if (width === 1440 || width === 390) await page.screenshot({ path: `output/playwright/sync-${path.startsWith('/growth') ? 'growth' : 'review'}-${width}.png`, fullPage: true })
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('http://127.0.0.1:5188/growth')
  const day = page.locator('.growth-heat-grid button[title^="2026-09-13"]')
  await day.click()
  check(await page.locator('.growth-record-list li').count() === 1, 'Day filter failed')
  await day.click()
  check(await page.locator('.growth-record-list li').count() === 2, 'Day toggle failed')
  await page.locator('.growth-record-list li').first().getByRole('button').click()
  await page.waitForURL('**/ai-review?sessionId=11&feedbackId=101')
  await page.getByLabel('课堂转写', { exact: true }).fill('保留的合成课堂证据')
  await page.getByLabel('教师备注', { exact: true }).fill('核对教师自纠')
  await page.getByRole('button', { name: '修改后重新生成', exact: true }).click()
  await page.locator('.review-rail__actions .error').waitFor()
  check(generated.length === 1 && generated[0].transcript_text === '保留的合成课堂证据', 'Review material input disconnected')
  await page.locator('.review-list li').filter({ hasText: '合成课堂乙' }).getByRole('button').click()
  await page.getByRole('heading', { name: '当前材料暂时无法评分' }).waitFor()
  check((await page.locator('.review-stat--score strong').innerText()).trim() === '—', 'Missing evidence displayed as zero')
  await page.locator('.review-list li').filter({ hasText: '合成课堂甲' }).getByRole('button').click()
  await page.waitForURL('**/ai-review?sessionId=11&feedbackId=101')
  await page.waitForFunction(() => document.querySelector('.review-materials textarea')?.value === '保留的合成课堂证据')
  check(await page.getByLabel('课堂转写', { exact: true }).inputValue() === '保留的合成课堂证据', 'Switching reports lost the draft')
  await page.reload()
  await page.getByLabel('课堂转写', { exact: true }).waitFor()
  check(await page.getByLabel('课堂转写', { exact: true }).inputValue() === '保留的合成课堂证据', 'Reload lost the draft')
  growthFails = true
  await page.goto('http://127.0.0.1:5188/growth')
  await page.getByRole('alert').filter({ hasText: '合成验收：成长加载失败' }).waitFor()
  check(await page.locator('.growth-record-list li').count() === 0, 'Failed growth request fabricated records')
  check(errors.length === 0, `Page errors: ${errors.join('; ')}`)
  return { result: failures.length ? 'FAILED' : 'PASSED', failures, errors, layouts, mockedGenerationRequests: generated.length }
}
