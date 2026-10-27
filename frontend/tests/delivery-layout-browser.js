// Run with playwright-cli run-code --filename=frontend/tests/delivery-layout-browser.js.
// Uses the actual production entry and mocks API data; no devices or real model calls.
async (page) => {
  const errors = [], missingAssets = [], results = [];
  const check = (value, message) => { if (!value) throw Error(message); };
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (r.status() >= 400 && /\/(assets|models)\//.test(r.url())) missingAssets.push(r.url()); });
  const titles = ['导入技能','板书板画技能','演示技能','讲解技能','提问技能','强化技能','结束技能','组织技能','变化技能','综合模拟授课'];
  const courses = titles.map((title,i) => ({id:i+1,title,stage:i<9?'专项0'+(i+1):'综合',category:i<9?'专项':'综合',description:'生产页面验收用模拟课程',lesson_count:8,progress_percent:i===3?38:0,status:i===3?'in_progress':'not_started',outline:'教学目标\n课堂练习',source:'隔离验收数据'}));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data = {items:[]};
    if(path === '/api/auth/me') data={id:-27,name:'林晓',role_label:'模拟验收'};
    if(path === '/api/courses') data={items:courses};
    if(path === '/api/dashboard/overview') data={greeting:{name:'林晓'},weekly_training:{sessions:3,total_minutes:26},quick_entries:[{title:'课程中心',icon:'▤',route:'/courses'},{title:'模拟授课',icon:'▶',route:'/classroom'},{title:'资源库',icon:'▥',route:'/resources'},{title:'成长档案',icon:'↗',route:'/growth'}],growth_trajectory:[68,75,82]};
    if(path === '/api/growth')data={points:[],records:[],heatmap:[],milestones:[],summaries:[],journals:[]};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(() => {
    localStorage.setItem('link_token','isolated-layout-fixture');
    localStorage.setItem('link_tour:-27:2026-10-1','skipped');
    localStorage.setItem('link-ui-version','studio');
  });
  const measure = () => page.evaluate(() => {
    const rect = selector => { const r=document.querySelector(selector).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}; };
    return {sidebar:rect('.app-shell > .sidebar'),workspace:rect('.app-shell > .workspace'),page:rect('.page-frame'),width:innerWidth,height:innerHeight};
  });
  for(const origin of ['http://127.0.0.1:5193','http://127.0.0.1:5194']) {
    const mode=origin.endsWith('5194')?'production':'development';
    for(const theme of ['classic','academy']) {
      for(const route of ['/resources','/dashboard','/courses','/classroom','/growth','/knowledge','/profile','/ai-review']) {
        await page.goto(origin+route);
        await page.getByRole('combobox',{name:'界面风格',exact:true}).selectOption(theme);
        await page.waitForFunction(t=>document.documentElement.dataset.uiTheme===t,theme);
        await page.locator('.page-slot > *').first().waitFor();
        for(const [width,height] of [[1280,720],[1366,768],[1440,900],[1920,1080],[390,844]]) {
          await page.setViewportSize({width,height});
          const m=await measure();
          if(width>700) {
            check(m.sidebar.width<=250 && m.sidebar.width>=60,JSON.stringify({mode,theme,route,issue:'sidebar width',m}));
            check(Math.abs(m.sidebar.y-m.workspace.y)<5 && m.workspace.x>=m.sidebar.right-2,JSON.stringify({mode,theme,route,issue:'grid displaced',m}));
            check(m.workspace.width>=width*.6 && m.page.width>500,JSON.stringify({mode,theme,route,issue:'content squeezed',m}));
          } else check(m.workspace.x>=-1 && m.workspace.right<=width+1 && m.page.width>=width*.8,'mobile content clipped '+JSON.stringify(m));
          if(route==='/courses')check(m.page.height>=height*.8,'desk height collapsed '+JSON.stringify({mode,theme,m}));
          if(route==='/dashboard' && width>700)check(await page.locator('.page-dashboard').evaluate(e=>e.scrollHeight<=e.clientHeight+2),'dashboard scroll');
          results.push({mode,theme,route,width,sidebarWidth:m.sidebar.width,contentWidth:m.page.width});
          if(mode==='production' && [1280,390].includes(width) && ['/resources','/dashboard','/courses'].includes(route)) {
            await page.waitForTimeout(450);
            await page.screenshot({path:`output/playwright/production-${route.slice(1)}-${theme}-${width}.png`});
          }
        }
      }
    }
    await page.goto(origin+'/courses');await page.setViewportSize({width:1280,height:720});
    const items=page.locator('.course-desk__labels button');await items.first().waitFor();
    check(await items.count()===10,'missing desk objects');
    for(let i=0;i<10;i++){await items.nth(i).click();await page.locator('dialog[open]').waitFor();await page.keyboard.press('Escape');check(await items.nth(i).evaluate(e=>e===document.activeElement),'focus return');}
    await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('original');
    await page.waitForFunction(()=>!document.querySelector('.app-shell').classList.contains('studio-ui'));
    const legacy=await measure();check(legacy.sidebar.width<250 && legacy.workspace.x>=legacy.sidebar.right-2,'original layout displaced');
  }
  check(errors.length===0,'runtime errors: '+errors.join(';'));
  check(missingAssets.length===0,'missing assets: '+missingAssets.join(';'));
  return {checks:results.length,errors,missingAssets,examples:results.filter(r=>r.route==='/resources'&&r.mode==='production')};
}
