// Run with: playwright-cli -s=classroom-ui run-code --filename scripts/qa-classroom-ui.js
// Browser-only synthetic state. No real accounts, device access, or paid requests.
async (page) => {
  const failures = [], errors = [], requests = [];
  const check = (value, message) => { if (!value) failures.push(message); };
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.dismiss());
  await page.addInitScript(() => {
    localStorage.setItem('link_token', 'synthetic-ui-only');
    window.__deviceRequests = 0;
    navigator.mediaDevices.getUserMedia = async () => { window.__deviceRequests++; throw new Error('UI test: devices disabled'); };
  });
  const service = { configured: true, pricing_confirmed: true, provider: 'openai_next', model: 'deepseek-v4-flash', status: 'available' };
  const capabilities = { pose_assets: true, services: {
    dialogue: { ...service }, vision: { ...service, model: 'deepseek-v4-flash-vision-exp' },
    asr: { ...service, provider: 'xfyun', status: 'unverified', model: 'slm / iat-v1' },
    tts: { ...service, provider: 'xfyun', status: 'unverified', model: 'online-tts-v2' }
  }, budget: { pricing_confirmed: true, stopped: false, warning: false, spent_and_reserved_cny: 1.7414, limit_cny: 100, stop_cny: 90,
    credits: { accounts: Object.fromEntries([['dialogue','模拟授课 / 评课',30],['vision','视觉',40],['test','测试',30]].map(([key,label,limit]) => [key,{ label, limit_usd: limit, stop_usd: limit * .9, spent_and_reserved_usd: .0001, stopped: false, warning: false }])) }
  }};
  await page.route('**/*', async route => {
    const request = route.request();
    if (!/^http:\/\/(127\.0\.0\.1|localhost):5188\//.test(request.url())) return route.abort();
    const url = { pathname: request.url().replace(/^http:\/\/[^/]+/, '').split('?')[0] };
    if (url.pathname.startsWith('/api/')) {
      requests.push({ path: url.pathname, method: request.method() });
      if (request.method() !== 'GET') return route.fulfill({ status: 400, json: { message: 'Synthetic UI: writes blocked' } });
      if (url.pathname === '/api/classroom/capabilities') return route.fulfill({ json: capabilities });
      if (url.pathname === '/api/classroom/sessions') return route.fulfill({ json: { items: [] } });
      if (url.pathname === '/api/auth/me') return route.fulfill({ json: { id: 1, name: '林晓', role_label: '师范生' } });
      if (url.pathname.includes('/evidence/')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect width="320" height="480" fill="#7952b3"/><rect x="320" width="320" height="480" fill="#ff7a18"/></svg>' });
      return route.fulfill({ status: 404, json: { message: 'Synthetic UI fixture' } });
    }
    if (url.pathname === '/src/services/useClassroom.js') {
      const response = await route.fetch();
      const source = await response.text();
      const instrumented = source.replace('  return {\n    room,', '  return window.__classroomQA = {\n    room,');
      if (source === instrumented) throw new Error('Could not instrument classroom refs');
      return route.fulfill({ response, body: instrumented });
    }
    return route.continue();
  });
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.getByRole('heading', { name: '模拟课堂' }).waitFor();
  await page.waitForFunction(() => window.__classroomQA?.capabilities.value);
  await page.waitForTimeout(500);
  check(await page.getByRole('button', { name: '开始课堂' }).isDisabled(), 'Consent must gate start');
  check(await page.getByText('待检查', { exact: true }).first().isVisible(), 'Unverified speech must remain pending');
  check(!await page.locator('#classroom-settings').isVisible(), 'Settings must start collapsed');
  check(!await page.getByRole('checkbox', { name: '云端画面分析' }).isChecked(), 'Cloud vision must default off');
  await page.getByRole('checkbox', { name: '同意语音识别与 AI 评课' }).check();
  check(await page.getByRole('button', { name: '开始课堂' }).isEnabled(), 'Consent should enable configured classroom');
  const layouts = [];
  for (const width of [1440,1024,768,320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1080 : 900 });
    await page.waitForTimeout(150);
    const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      startBottom: [...document.querySelectorAll('.class-controls button')][0]?.getBoundingClientRect().bottom,
      background: getComputedStyle(document.querySelector('.class-stage')).backgroundColor }));
    layouts.push(layout);
    check(layout.scrollWidth <= width, `Horizontal overflow at ${width}: ${layout.scrollWidth}`);
    await page.screenshot({ path: `output/playwright/classroom-${width}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.locator('.settings-toggle').click();
  check(await page.locator('#classroom-settings').isVisible(), 'Settings should expand');
  check(await page.getByText('额度详情', { exact: true }).isVisible(), 'Budget details missing');
  await page.screenshot({ path: 'output/playwright/classroom-settings.png', fullPage: true });
  await page.locator('.settings-toggle').click();
  await page.getByRole('button', { name: '历史课堂', exact: true }).click();
  check(await page.getByText('暂无课堂记录', { exact: true }).isVisible(), 'History empty state missing');
  await page.getByRole('button', { name: '收起历史', exact: true }).click();
  await page.evaluate(() => {
    const live = window.__classroomQA;
    live.capabilities.value.budget.credits.accounts.vision.stopped = true;
    live.capabilities.value.budget.credits.accounts.vision.warning = true;
  });
  check(await page.getByText(/视觉额度达到停止线/).isVisible(), 'Optional account warning must be visible when collapsed');
  await page.evaluate(() => { const live=window.__classroomQA; live.capabilities.value.budget.credits.accounts.vision.stopped=false; live.capabilities.value.budget.credits.accounts.vision.warning=false;
    live.capabilities.value.services.asr.status='failed'; live.capabilities.value.services.asr.message='语音连接失败，请重试。'; });
  check(await page.getByText('部分服务待处理，请检查连接设置。').isVisible(), 'Failed connection should be actionable');
  await page.evaluate(() => {
    const live=window.__classroomQA;
    live.capabilities.value.services.asr.status='unverified';
    live.room.value={ session_id: 900, state: 'active', elapsed: 120, mode: 'full', students: {} };
    live.state.value='listening'; live.partial.value='同学们，怎样把这块蛋糕平均分给两个人？';
  });
  check(await page.getByRole('button', { name: '结束并评课' }).isVisible(), 'Live controls missing');
  await page.evaluate(() => { const live=window.__classroomQA; live.state.value='speaking'; live.activeStudent.value='ming'; live.raised.value='yu';
    live.events.value=[{id:1,type:'transcript',at_ms:1000,data:{text:'同学们，怎样把这块蛋糕平均分给两个人？'}},{id:2,type:'student',at_ms:5000,data:{name:'小明',text:'老师，每个人分到一样大的一块，就是平均分。'}}]; });
  check(await page.getByRole('button', { name: '打断学生' }).isVisible(), 'Interrupt control missing');
  await page.screenshot({ path: 'output/playwright/classroom-speaking.png', fullPage: true });
  await page.evaluate(() => { const live=window.__classroomQA; live.state.value='finishing'; });
  check(await page.getByRole('button', { name: '结束处理中…' }).isDisabled(), 'Finish must not repeat');
  await page.evaluate(() => { const live=window.__classroomQA; live.state.value='disconnected'; live.activeStudent.value=null; live.error.value='连接已断开，请重新连接。'; });
  check(await page.getByRole('button', { name: '重新连接', exact: true }).isVisible(), 'Reconnect missing');
  await page.evaluate(() => {
    const live=window.__classroomQA; live.state.value='ended'; live.partial.value=''; live.error.value=''; live.raised.value=null;
    const events=[{id:1,type:'transcript',at_ms:1000,data:{text:'每份一样大，才是平均分。'}},{id:2,type:'playback',at_ms:5000,data:{status:'playback_completed'}},{id:3,type:'vision',at_ms:15000,data:{observations:'教师展示了等分示意图。'}}];
    live.events.value=events;
    live.room.value={session_id:900,state:'ended',mode:'full',elapsed:600,students:{},events,report_state:'completed',report_version:1,
      report:{overall_score:86,coverage:'2/6',sources:[],dimensions:[{key:'clarity',label:'表达清晰度',score:86,reason:'能通过对比说明平均分，表达清楚。',event_ids:[1,2,3],source_ids:[]},{key:'posture',label:'教态与站位',score:null,reason:'暂无足够证据。',event_ids:[],source_ids:[]}]}};
  });
  await page.getByRole('heading', { name: '课堂评课', exact: true }).waitFor();
  check(!await page.locator('#evidence-2').count(), 'Technical event should start hidden');
  await page.getByRole('button', { name: '↗ 0:05', exact: true }).click();
  check(await page.locator('#evidence-2').isVisible(), 'Report jump must reveal technical evidence');
  check(await page.locator('#evidence-2').evaluate(el => document.activeElement === el), 'Report jump must focus evidence');
  await page.getByRole('button', { name: '↗ 0:15', exact: true }).click();
  await page.getByRole('dialog', { name: '课堂截图证据' }).waitFor();
  await page.keyboard.press('Tab');
  check(await page.evaluate(() => Boolean(document.activeElement.closest('dialog'))), 'Dialog focus must stay contained');
  await page.screenshot({ path: 'output/playwright/classroom-evidence.png', fullPage: true });
  await page.keyboard.press('Escape');
  check(!await page.getByRole('dialog').count(), 'Escape should close evidence');
  await page.getByRole('heading', { name: '课堂评课', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'output/playwright/classroom-report.png', fullPage: true });
  await page.evaluate(() => { window.__classroomQA.room.value.report_state='running'; });
  check(await page.getByText('正在生成报告，可稍后在历史课堂查看。').isVisible(), 'Report loading missing');
  await page.evaluate(() => { window.__classroomQA.room.value.report_state='failed'; window.__classroomQA.room.value.report_error='报告生成超时，请重试。'; });
  check(await page.getByText('报告生成超时，请重试。').isVisible(), 'Report failure missing');
  check(await page.getByRole('button', { name: '重新评课', exact: true }).isEnabled(), 'Report retry missing');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  check(await page.locator('.student-eyes').first().evaluate(el=>getComputedStyle(el).animationName) === 'none', 'Reduced motion missing');
  check(await page.evaluate(() => window.__deviceRequests) === 0, 'No devices should be requested');
  check(!requests.some(request=>request.method!=='GET'), 'No paid or write requests should run');
  check(errors.length===0, `Browser errors: ${errors.join('; ')}`);
  return { layouts, failures, errors, requests, result: failures.length ? 'FAILED' : 'PASSED' };
}
