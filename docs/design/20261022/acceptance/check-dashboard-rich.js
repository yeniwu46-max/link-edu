async(page)=>{
 const check=(v,m)=>{if(!v)throw Error(m)},out=[];
 await page.goto('http://127.0.0.1:5188/tests/model-pages-browser.html?page=/courses');
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('studio');
 await page.evaluate(()=>{
  window.__studioFixture.setOverview({
   greeting:{name:'林晓 Alexandra 很长的测试姓名'},weekly_training:{sessions:12,total_minutes:150,sparkline:[8,9,11]},
   continue_training:{course_id:4,course_title:'讲解技能：帮助学生理解抽象概念',category:'专项',status_label:'进行中',progress_percent:38},
   ai_feedback:{id:13,overall_score:82,course_title:'讲解技能',suggestion:'先用具体实例引出抽象概念，再让学生解释自己的理解。'.repeat(30),dimensions:[{key:'a',label:'教学设计',score:88},{key:'b',label:'师生互动',score:78},{key:'c',label:'表达',score:84}]},
   quick_entries:[{title:'课程中心',icon:'▤',route:'/courses'},{title:'模拟授课',icon:'▶',route:'/classroom'},{title:'资源库',icon:'▥',route:'/resources'},{title:'成长档案',icon:'↗',route:'/growth'}],
   growth_trajectory:[65,72,69,78,85,82]
  });return window.__studioFixture.router.push('/dashboard');
 });
 await page.waitForSelector('.feedback .score');await page.waitForTimeout(800);
 const skip=page.getByRole('button',{name:'跳过',exact:true});if(await skip.isVisible())await skip.click();
 for(const theme of ['classic','academy'])for(const [width,height]of [[1280,720],[1366,768],[1440,900],[390,844]]){
  await page.setViewportSize({width,height});await page.getByRole('combobox',{name:'界面风格',exact:true}).selectOption(theme);
  await page.waitForTimeout(650);const m=await page.evaluate(()=>{let d=document.querySelector('.page-dashboard'),p=document.querySelector('.feedback>p'),w=document.querySelector('.welcome');return{scroll:d.scrollHeight,client:d.clientHeight,greeting:w.getBoundingClientRect().height,lineClamp:getComputedStyle(p).webkitLineClamp,font:getComputedStyle(w.querySelector('h1')).fontSize,overflowX:document.documentElement.scrollWidth>innerWidth}});
  if(width>700)check(m.scroll<=m.client+2,'rich dashboard scroll '+JSON.stringify({theme,width,...m}));
  check(!m.overflowX&&m.lineClamp==='3','long content overflow');out.push({theme,width,...m});
  await page.screenshot({path:'docs/design/20261022/compact-implemented/dashboard-content-'+theme+'-'+width+'.png'});
 }
 await page.setViewportSize({width:1280,height:720});if(await skip.isVisible())await skip.click();await page.locator('.feedback').click();check((await page.locator('.feedback-sheet__hero p').innerText()).length>500,'full feedback missing');await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.setViewportSize({width:1280,height:480});
 check(await page.locator('.page-dashboard').evaluate(e=>e.scrollHeight>e.clientHeight),'short viewport clips content');
 await page.setViewportSize({width:1280,height:720});await page.emulateMedia({reducedMotion:'reduce'});
 check(await page.locator('.paper-title__letter').first().evaluate(e=>getComputedStyle(e).animationName==='none'),'motion preference ignored');
 for(const route of ['/classroom','/courses','/resources','/growth','/profile','/knowledge','/ai-review']){
  await page.evaluate(r=>window.__studioFixture.router.push(r),route);
  await page.locator('.page-slot h1').waitFor({state:'attached'});check(await page.locator('.page-slot h1').first().evaluate(e=>e.classList.contains('sr-only')),'visible title '+route);
 }
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('original');
 await page.waitForFunction(()=>!document.querySelector('.page-slot h1').classList.contains('sr-only'));
 return out;
}
