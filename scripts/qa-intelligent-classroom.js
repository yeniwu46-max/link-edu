// playwright-cli -s=link-intelligence-qa run-code --filename scripts/qa-intelligent-classroom.js --raw
// Synthetic, read-only browser check for evidence trace, simulated state and practice entry.
async (page) => {
  await page.unrouteAll({behavior: 'ignoreErrors'});
  page.removeAllListeners('pageerror');
  const errors = [], failures = [], writes = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('link_token', 'synthetic-intelligence-only');
    window.__devices = 0;
    navigator.mediaDevices.getUserMedia = async () => { window.__devices++; throw Error('QA blocks devices'); };
  });
  const scenario = {id: 'primary-math-fractions', version: 1, topic: '分数的初步认识', grade: '小学三年级',
    objective: '解释平均分并回应典型误解。', students: {ming: {focus: '喜欢追问'}, yu: {focus: '误以为不等分也可以表示二分之一'}, lin: {focus: '点名后回应'}}};
  const plan = {id: 1, source_session_id: 900, source_report_version: 1, dimension: 'structure',
    target_kind: 'teacher_summary', task_text: '在课末回顾本节目标与关键概念。', basis: 'report_evidence',
    source_event_ids: [1], status: 'suggested', retest_session_id: null, comparison: null};
  const events = [
    {id: 1, type: 'transcript', at_ms: 1000, data: {text: '平均分就是每份同样多。'}},
    {id: 2, type: 'student_state_transition', at_ms: 1400, data: {student_id: 'yu', event_ids: [1],
      before: {concept_states: {equal_parts: 'misconception'}},
      after: {understanding: '每份必须同样多', misconceptions: [], concept_states: {equal_parts: 'addressed'}}}},
    {id: 3, type: 'transcript', at_ms: 2500, data: {text: '这节课我们学习了平均分。'}},
  ];
  const room = {session_id: 900, topic: scenario.topic, mode: 'full', state: 'ended', elapsed: 90,
    created_at: '2026-10-04T08:00:00', report_state: 'completed', report_version: 1, students: {}, events,
    report: {overall_score: 72, generated_at: '2026-10-04T08:02:00',
      dimensions: [{key: 'structure', score: 72, reason: '课堂结尾进行了小结。', event_ids: [3], source_ids: []}], sources: []},
    behavior_analysis: {version: 'teaching-behavior-1', coverage: {teacher_transcripts: 2, completed_student_replies: 0, vision_samples: 0, observed_motion_samples: 0},
      segments: [{kind: 'teacher_summary', start_ms: 2500, end_ms: 2500, event_ids: [3], detail: '这节课我们学习了平均分。'}]},
    practice_plans: [plan]};
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== 'http://127.0.0.1:5188') return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    if (request.method() !== 'GET') { writes.push(url.pathname); return route.fulfill({status: 400, json: {message: 'QA blocks writes'}}); }
    if (url.pathname === '/api/auth/me') return route.fulfill({json: {id: 1, name: '测试教师', role_label: '师范生'}});
    if (url.pathname === '/api/classroom/capabilities') return route.fulfill({json: {services: {}, budget: {}, scenario}});
    if (url.pathname === '/api/classroom/sessions') return route.fulfill({json: {items: [{...room, events: undefined}]}});
    if (url.pathname === '/api/classroom/sessions/900') return route.fulfill({json: room});
    if (url.pathname === '/api/classroom/practice-plans/1') return route.fulfill({json: plan});
    return route.fulfill({status: 404, json: {message: 'Synthetic fixture not found'}});
  });
  await page.setViewportSize({width: 1280, height: 900});
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=900');
  await page.getByRole('heading', {name: '一节课的教学剖面'}).waitFor();
  check(await page.getByRole('heading', {name: '可回放的教学行为'}).isVisible(), 'Behavior section missing');
  check(await page.getByRole('heading', {name: '模拟学生状态变化'}).isVisible(), 'Student transition section missing');
  check(await page.getByText('每份必须同样多', {exact: false}).count() > 0, 'Student state text missing');
  check(await page.getByRole('heading', {name: '带着目标再练一次'}).isVisible(), 'Practice section missing');
  await page.getByRole('button', {name: '查看教师证据'}).click();
  await page.getByRole('dialog', {name: '状态变化 · 教师证据'}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('link', {name: '开始这项复练'}).click();
  await page.getByRole('heading', {name: '本次训练目标'}).waitFor();
  check(await page.getByText(plan.task_text, {exact: true}).isVisible(), 'Selected practice task missing on classroom entry');
  await page.setViewportSize({width: 320, height: 800});
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Practice entry overflows at 320px');
  await page.screenshot({path: 'output/playwright/intelligent-classroom-practice.png', fullPage: true});
  check(await page.evaluate(() => window.__devices) === 0, 'Read-only flow requested media devices');
  check(writes.length === 0, 'Read-only flow made a write request');
  check(errors.length === 0, `Browser errors: ${errors.join('; ')}`);
  return {result: failures.length ? 'FAILED' : 'PASSED', failures, errors};
}
