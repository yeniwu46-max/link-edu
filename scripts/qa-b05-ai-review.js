// Run with: playwright-cli -s=b05-ai-review run-code --filename scripts/qa-b05-ai-review.js
// Synthetic browser acceptance only. All API responses are intercepted; no DeepSeek request is sent.
async (page) => {
  const failures = []
  const errors = []
  const requests = []
  const check = (value, message) => { if (!value) failures.push(message) }
  const json = (body) => JSON.stringify(body)

  const reports = {
    demo: {
      demo: true,
      source: 'demo',
      mode_label: '片段练习',
      generation_status: undefined,
      overall_score: 72,
      dimensions: [{ key: 'clarity', label: '表达清晰度', score: 72, evidence: '规则评分' }],
      sections: [{ title: '综合判断', body: '历史演示报告。' }],
    },
    real: {
      demo: false,
      source: 'deepseek',
      generation_status: 'succeeded',
      overall_score: 82,
      dimensions: [{ key: 'clarity', label: '表达清晰度', score: 82, evidence: '课堂转写' }],
      sections: [{ title: '综合判断', body: '真实报告。' }],
    },
    insufficient: {
      demo: false,
      source: 'deepseek',
      generation_status: 'succeeded',
      insufficient_evidence: true,
      overall_score: null,
      dimensions: [{ key: 'clarity', label: '表达清晰度', score: 0, evidence: '证据不足' }],
      sections: [{ title: '综合判断', body: '证据不足。' }],
    },
  }
  let items = [
    { id: 101, session_id: 11, course_title: '演示课程', created_at: '2026-09-01T10:00:00Z', overall_score: 72, report: { ...reports.demo } },
    { id: 102, session_id: 12, course_title: '真实课程', created_at: '2026-09-02T10:00:00Z', overall_score: 82, report: { ...reports.real } },
    { id: 103, session_id: 13, course_title: '材料不足课程', created_at: '2026-09-03T10:00:00Z', overall_score: null, report: { ...reports.insufficient } },
  ]
  let generationRequests = 0
  let askRequests = 0
  let delayedAskResolve = null
  let sendUnauthorized = false

  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (request.url().includes('/api/')) requests.push({ path: request.url(), method: request.method(), body: request.postData() })
  })
  await page.addInitScript(() => localStorage.setItem('link_token', 'synthetic-b05-token'))
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (!url.pathname.startsWith('/api/')) return route.continue()

    if (url.pathname === '/api/auth/me' && request.method() === 'GET') {
      return route.fulfill({ json: { id: 1, name: '测试教师', role_label: '师范生' } })
    }
    if (url.pathname === '/api/feedbacks' && request.method() === 'GET') {
      return route.fulfill({ json: { items } })
    }
    if (url.pathname.includes('/ai-review') && request.method() === 'POST') {
      generationRequests += 1
      const payload = JSON.parse(request.postData() || '{}')
      check(payload.transcript_text === '课堂转写证据', 'Generation must submit transcript_text')
      check(payload.teacher_notes === '关注等待时间', 'Generation must submit teacher_notes')
      if (generationRequests === 1) {
        await new Promise((resolve) => setTimeout(resolve, 350))
        const next = { ...items[1], report: { ...reports.real, overall_score: 86 }, overall_score: 86 }
        items = items.map((item) => item.id === 102 ? next : item)
        return route.fulfill({ json: { feedback: next } })
      }
      const failed = {
        ...items[1],
        report: {
          ...reports.real,
          generation_status: 'failed',
          generation_error: 'AI 评课生成失败，请稍后重试',
          overall_score: 86,
        },
      }
      items = items.map((item) => item.id === 102 ? failed : item)
      return route.fulfill({ status: 502, json: { message: 'AI 评课生成失败，请检查配置后重试' } })
    }
    if (url.pathname.includes('/ask') && request.method() === 'POST') {
      askRequests += 1
      if (sendUnauthorized) return route.fulfill({ status: 401, json: { message: '登录状态已失效' } })
      if (askRequests === 2) {
        await new Promise((resolve) => { delayedAskResolve = resolve })
      }
      return route.fulfill({ json: { feedback_id: 103, scope: 'current', answer: '请补充学生回应和等待时间。' } })
    }
    return route.fulfill({ status: 404, json: { message: 'Synthetic B-05 fixture' } })
  })

  await page.setViewportSize({ width: 1440, height: 1080 })
  await page.goto('http://127.0.0.1:5188/ai-review?sessionId=12&feedbackId=102')
  await page.getByRole('combobox', { name: '选择评课报告' }).waitFor()
  check(await page.getByRole('combobox', { name: '选择评课报告' }).inputValue() === '102', 'URL-selected report must survive initial load')
  await page.getByRole('combobox', { name: '选择评课报告' }).selectOption('101')
  await page.waitForTimeout(100)
  check(page.url().includes('feedbackId=101') && page.url().includes('sessionId=11'), 'History selection must sync URL')
  await page.reload()
  await page.getByRole('combobox', { name: '选择评课报告' }).waitFor()
  check(await page.getByRole('combobox', { name: '选择评课报告' }).inputValue() === '101', 'Refresh must restore the URL-selected report')

  await page.getByRole('combobox', { name: '选择评课报告' }).selectOption('102')
  await page.locator('textarea').nth(0).fill('课堂转写证据')
  await page.locator('textarea').nth(1).fill('关注等待时间')
  await page.getByRole('button', { name: '生成 DeepSeek 评课' }).click()
  check(await page.getByText('DeepSeek 正在生成').isVisible(), 'Generating state must be visible before response')
  await page.getByText('真实报告').waitFor()
  check(await page.getByText('生成 DeepSeek 评课').count() === 0, 'Successful generation should replace the initial action label')

  await page.locator('textarea').nth(0).fill('再次提交证据')
  await page.getByRole('button', { name: '修改后重新生成' }).click()
  await page.getByText('失败可重试').waitFor()
  check(await page.getByText('上一次生成没有完成，课堂材料已保留，可以直接重试。').isVisible(), 'Failed generation must preserve retry state')

  await page.getByRole('combobox', { name: '选择评课报告' }).selectOption('103')
  await page.getByText('当前材料暂时无法评分').waitFor()
  await page.locator('textarea').nth(2).fill('需要补充什么证据？')
  await page.getByRole('button', { name: '发送问题' }).click()
  await page.getByText('请补充学生回应和等待时间。').waitFor()
  check(await page.getByText('当前材料暂时无法评分').isVisible(), 'Insufficient evidence report must remain visible after follow-up')

  await page.getByRole('combobox', { name: '选择评课报告' }).selectOption('102')
  const delayed = page.locator('textarea').nth(2)
  await delayed.fill('旧报告问题')
  askRequests = 1
  const askPromise = page.getByRole('button', { name: '发送问题' }).click()
  await page.waitForTimeout(100)
  await page.getByRole('combobox', { name: '选择评课报告' }).selectOption('103')
  check((await page.getByText('请补充学生回应和等待时间。').count()) === 0, 'Switching reports must clear the previous answer')
  if (delayedAskResolve) delayedAskResolve()
  await askPromise
  check((await page.getByText('旧报告问题').count()) === 0, 'Late follow-up response must not appear on the new report')

  sendUnauthorized = true
  await page.getByRole('button', { name: '发送问题' }).click()
  await page.waitForTimeout(100)
  check(await page.url().endsWith('/'), '401 must return to the login route')

  const layouts = []
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: width > 700 ? 900 : 844 })
    layouts.push(await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth })))
    check(layouts.at(-1).scrollWidth <= width, `Horizontal overflow at ${width}px`)
  }
  check(errors.length === 0, `Browser errors: ${errors.join('; ')}`)
  return { layouts, generationRequests, askRequests, failures, errors, requests, result: failures.length ? 'FAILED' : 'PASSED' }
}
