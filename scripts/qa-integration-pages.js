// Synthetic browser QA only: every API request is intercepted; real devices and external traffic are blocked.
async (page) => {
  page.setDefaultTimeout(12000);
  page.setDefaultNavigationTimeout(15000);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  const failures = [], errors = [], requests = [], layouts = [];
  const check = (ok, label) => { if (!ok) failures.push(label); };
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('link_token', 'integration-synthetic-only');
    navigator.mediaDevices.getUserMedia = async () => { throw new Error('Devices blocked in integration QA'); };
  });
  const user = { id: 909, account: 'qa-only', name: '合并验收', role: 'student', role_label: '师范生', school: '', grade: '', major: '', bio: '', badges: [], recent_feedbacks: [] };
  const courses = [
    { id: 1, title: '导入：创设教学情境', description: '设计问题情境与学习目标。', category: '专项', stage: '专项01', lesson_count: 2, status_label: '未开始', progress_percent: 0, outline: '观察\n提问\n反思' },
    { id: 2, title: '提问：追问与候答', description: '练习有效提问。', category: '专项', stage: '专项05', lesson_count: 2, status_label: '未开始', progress_percent: 0 },
  ];
  const overview = { greeting: { name: user.name, subtitle: '准备好开始今天的模拟课堂了吗？' }, weekly_training: { sessions: 0, total_minutes: 0, sparkline: [], heatmap: [], month_heatmap: [], summaries: [], journals: [] }, continue_training: null, ai_feedback: null, growth_trajectory: [], growth_records: [], quick_entries: [
    { title: '我的课程', description: '2 门课程', icon: '▤', route: '/courses' },
    { title: '模拟课堂', description: '互动授课', icon: '◈', route: '/classroom' },
    { title: 'AI 评课', description: '课堂反馈', icon: '◔', route: '/ai-review' },
    { title: '资源中心', description: '教学素材', icon: '▣', route: '/resources' },
  ] };
  let resourceFailure = false, profileFailure = false, expired = false;
  await page.route('**/*', async route => {
    const req = route.request(), path = req.url().replace(/^http:\/\/[^/]+/, '').split('?')[0];
    if (!/^http:\/\/127\.0\.0\.1:5188\//.test(req.url())) return route.abort();
    if (!path.startsWith('/api/')) return route.continue();
    requests.push({ path, method: req.method() });
    if (expired) return route.fulfill({ status: 401, json: { message: '登录状态已失效，请重新登录' } });
    if (req.method() !== 'GET') {
      if (path === '/api/profile' && !profileFailure) return route.fulfill({ json: { ...user, ...req.postDataJSON() } });
      return route.fulfill({ status: 503, json: { message: '合成验收：保存失败，请重试' } });
    }
    const data = {
      '/api/auth/me': user, '/api/profile': user, '/api/courses': { items: courses },
      '/api/dashboard/overview': overview, '/api/feedbacks': { items: [] },
      '/api/growth': { points: [], heatmap: [], milestones: [], summaries: [], records: [] },
      '/api/classroom/sessions': { items: [] },
      '/api/resources': { items: [
        { id: 1, title: '缺少文件的资源', category: '教案', description: '空链接验收', file_url: '' },
        { id: 2, title: '不安全资源', category: '素材', file_url: 'javascript:alert(1)' },
        { id: 3, title: '课程资料', category: '教案', file_url: '/library/preview/ntce-primary.pdf' },
        { id: 4, title: '公开来源', category: '素材', file_url: 'https://example.org/lesson' },
      ] },
    };
    if (path === '/api/resources' && resourceFailure) return route.fulfill({ status: 503, json: { message: '合成验收：资源服务不可用' } });
    return route.fulfill(data[path] ? { json: data[path] } : { status: 404, json: { message: 'Synthetic fixture missing' } });
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const path of ['/dashboard', '/courses', '/resources', '/growth', '/profile']) {
      await page.goto(`http://127.0.0.1:5188${path}`);
      await page.locator('.page-frame .page-slot').waitFor();
      await page.waitForTimeout(400);
      const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, workspaceScroll: document.querySelector('.workspace').scrollWidth, workspaceWidth: document.querySelector('.workspace').clientWidth }));
      layouts.push({ path, ...layout });
      check(layout.scroll <= width && layout.workspaceScroll <= layout.workspaceWidth + 1, `Overflow at ${path} ${width}: ${JSON.stringify(layout)}`);
      if (width === 1440 || width === 390) await page.screenshot({ path: `output/playwright/integration-${path.slice(1)}-${width}.png`, fullPage: true });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('http://127.0.0.1:5188/dashboard');
  await page.locator('.continue-empty').waitFor();
  check(await page.locator('.feedback-empty').isVisible(), 'New account has no truthful feedback entry');
  check(await page.locator('.feedback .score').count() === 0, 'Empty dashboard invented a score');
  await page.getByRole('searchbox', { name: '搜索课程', exact: true }).fill('  提问  ');
  await page.getByRole('searchbox', { name: '搜索课程', exact: true }).press('Enter');
  await page.waitForURL('**/courses?q=*');
  await page.getByText('搜索“提问” · 1 个结果', { exact: true }).waitFor();
  check(await page.locator('.course-slab').count() === 1, 'Merged search lost filtering');
  await page.getByRole('searchbox', { name: '搜索课程', exact: true }).fill('找不到的课程');
  await page.getByRole('searchbox', { name: '搜索课程', exact: true }).press('Enter');
  await page.getByText('没有找到“找不到的课程”相关课程，请换个关键词。', { exact: true }).waitFor();
  await page.getByRole('button', { name: '清除搜索', exact: true }).click();
  await page.locator('.course-slab').first().getByRole('button', { name: '详情', exact: true }).click();
  check(await page.getByRole('dialog').isVisible(), 'Course detail missing');
  await page.getByRole('button', { name: '关闭', exact: true }).click();

  await page.goto('http://127.0.0.1:5188/resources');
  await page.getByRole('button', { name: '查看小学教师资格面试大纲', exact: true }).click();
  const reader = page.getByRole('dialog');
  check(await reader.isVisible(), 'PDF preview unavailable');
  check((await reader.getByRole('link', { name: '下载原文件' }).getAttribute('href')).endsWith('.doc'), 'Original DOC download lost');
  check(await reader.evaluate(el => el.open && el.parentElement === document.body), 'Reader is not a native top-level modal');
  await page.keyboard.press('Escape');
  check(await page.getByRole('button', { name: '查看小学教师资格面试大纲', exact: true }).evaluate(el => el === document.activeElement), 'Reader did not restore focus');
  await page.getByRole('tab', { name: '实操清单', exact: true }).click();
  await page.getByRole('button', { name: '查看教资面试着装与教姿实操清单', exact: true }).click();
  await page.locator('.markdown-reader').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '课程资源', exact: true }).click();
  await page.locator('.resource-list li').first().getByRole('button').click();
  await page.getByText('当前资源没有可用文件链接。', { exact: true }).waitFor();
  check(await page.getByRole('dialog').getByRole('link').count() === 0, 'Missing resource offered false download');
  await page.keyboard.press('Escape');
  await page.locator('.resource-list li').nth(1).getByRole('button').click();
  await page.getByText('文件链接无效，请联系管理员更新。', { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.locator('.resource-list li').nth(3).getByRole('button').click();
  check(await page.getByRole('link', { name: '访问来源网站', exact: true }).getAttribute('rel') === 'noopener noreferrer', 'External link security lost');
  check(await page.getByRole('link', { name: '下载文件', exact: true }).count() === 0, 'External link falsely claims file download');
  await page.keyboard.press('Escape');
  resourceFailure = true;
  await page.getByRole('button', { name: '精选资料', exact: true }).click();
  await page.getByRole('button', { name: '课程资源', exact: true }).click();
  await page.getByRole('button', { name: '重新加载资源', exact: true }).waitFor();
  resourceFailure = false;
  await page.getByRole('button', { name: '重新加载资源', exact: true }).click();
  await page.locator('.resource-list').waitFor();

  await page.goto('http://127.0.0.1:5188/profile');
  await page.getByLabel('学校', { exact: true }).waitFor();
  check(await page.getByLabel('学校', { exact: true }).inputValue() === '', 'Profile invented school');
  profileFailure = true;
  await page.getByLabel('姓名', { exact: true }).fill('保留的草稿');
  await page.getByRole('button', { name: '保存档案', exact: true }).click();
  await page.getByText('合成验收：保存失败，请重试', { exact: true }).waitFor();
  check(await page.getByLabel('姓名', { exact: true }).inputValue() === '保留的草稿', 'Failed profile save discarded draft');
  check(await page.getByText('档案已保存。', { exact: true }).count() === 0, 'Failed profile save reported success');
  await page.goto('http://127.0.0.1:5188/profile?tab=contact');
  check(await page.getByText('link-support@normal.edu', { exact: true }).count() === 0, 'Placeholder contact remains');
  await page.getByRole('button', { name: '记录问题', exact: true }).click();
  await page.getByLabel('问题内容', { exact: true }).fill('合并验收：仅存于测试拦截器');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await page.getByText(/问题保存失败：/).waitFor();
  check(await page.getByLabel('问题内容', { exact: true }).inputValue() !== '', 'Failed journal save lost draft');
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  expired = true;
  await page.goto('http://127.0.0.1:5188/dashboard');
  await page.waitForURL('http://127.0.0.1:5188/');
  check(await page.evaluate(() => localStorage.getItem('link_token')) === null, '401 did not clear token');
  check(await page.locator('input[autocomplete="username"]').inputValue() === '', 'Login still prefilled demo account');
  check(await page.locator('.social-btn').count() === 0, 'Unavailable social login still shown');
  check(errors.length === 0, `Browser errors: ${errors.join('; ')}`);
  await page.screenshot({ path: 'output/playwright/integration-landing.png', fullPage: true });
  return { result: failures.length ? 'FAILED' : 'PASSED', failures, errors, layouts, interceptedRequests: requests.length };
}
