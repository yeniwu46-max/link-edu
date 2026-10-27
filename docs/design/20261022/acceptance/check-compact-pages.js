async(page)=>{
 const check=(v,m)=>{if(!v)throw Error(m)},out=[];
 await page.goto('http://127.0.0.1:5188/tests/model-pages-browser.html?page=/dashboard');
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('studio');
 const skip=page.getByRole('button',{name:'跳过',exact:true});if(await skip.isVisible())await skip.click();
 for(const theme of ['classic','academy'])for(const [width,height] of [[1280,720],[1366,768],[1440,900]]){
  await page.setViewportSize({width,height});await page.getByRole('combobox',{name:'界面风格',exact:true}).selectOption(theme);
  const m=await page.evaluate(()=>{const d=document.querySelector('.page-dashboard'),w=document.querySelector('.welcome');return{scroll:d.scrollHeight,client:d.clientHeight,greeting:w.getBoundingClientRect().height,body:document.documentElement.scrollHeight,viewport:innerHeight}});
  check(m.scroll<=m.client+2,'dashboard scroll '+JSON.stringify({theme,width,...m}));check(m.greeting<70,'greeting too tall');out.push({theme,width,height,...m});
  await page.screenshot({path:'docs/design/20261022/compact-implemented/dashboard-'+theme+'-'+width+'.png'});
 }
 await page.getByRole('link',{name:'课程中心',exact:true}).click();await page.waitForSelector('.course-desk__texture');
 check(await page.locator('dialog[open]').count()===0,'entry unexpectedly opens modal');
 const stage=await page.locator('.course-desk').boundingBox(),workspace=await page.locator('.workspace').boundingBox();
 check(stage.height>=workspace.height-2&&stage.width>=workspace.width-2,'desk not filling workspace');
 const buttons=page.locator('.course-desk__labels button');
 for(let i=0;i<10;i++){
  await buttons.nth(i).click();await page.waitForSelector('dialog[open]');
  check(await buttons.nth(i).getAttribute('aria-pressed')==='true','highlight missing');
  await page.keyboard.press('Tab');check(await page.evaluate(()=>document.activeElement.closest('dialog')!==null),'focus escaped');
  await page.keyboard.press('Escape');check(await buttons.nth(i).evaluate(e=>e===document.activeElement),'focus not restored');
 }
 await buttons.nth(9).click();await page.getByRole('combobox',{name:'选择本类课程'}).selectOption('11');
 check((await page.locator('#course-modal-title').innerText()).includes('教资'),'course choice lost');
 await page.screenshot({path:'docs/design/20261022/compact-implemented/course-modal.png'});await page.keyboard.press('Escape');
 await page.getByRole('searchbox',{name:'搜索课程或桌面物件'}).fill('黑板');check(await page.locator('.course-desk__labels button:not(:disabled)').count()===1,'filter mismatch');
 await page.getByRole('searchbox',{name:'搜索课程或桌面物件'}).fill('');
 await page.getByRole('button',{name:'全部课程 ↗',exact:true}).click();check(await page.locator('.desk-directory li').count()===11,'directory missing courses');await page.keyboard.press('Escape');
 for(const theme of ['classic','academy']){
  await page.getByRole('combobox',{name:'界面风格',exact:true}).selectOption(theme);
  await page.screenshot({path:'docs/design/20261022/compact-implemented/desk-'+theme+'.png'});
 }
 await page.getByRole('button',{name:'提问 · 提示卡',exact:true}).click();await page.getByRole('button',{name:'开始训练 ↗',exact:true}).click();
 await page.waitForSelector('.classroom-course-context');check(await page.evaluate(()=>window.__studioFixture.router.currentRoute.value.query.courseId)==='5','lost course route');
 await page.getByRole('button',{name:'对话布局',exact:true}).click();await page.waitForSelector('.student-stage[data-renderer="ready"]');
 const seats=await page.locator('[data-student-viewport]').evaluateAll(es=>es.map(e=>{let r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom}}));
 check(seats.every(s=>s.h>60&&s.bottom<900),'seat clipped desktop');
 await page.screenshot({path:'docs/design/20261022/compact-implemented/classroom-academy.png'});
 await page.setViewportSize({width:390,height:844});
 const mobile=await page.locator('[data-student-viewport]').evaluateAll(es=>es.map(e=>{let r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom}}));
 check(mobile.every(s=>s.h>40&&s.w>50)&&Math.max(...mobile.map(s=>s.y))-Math.min(...mobile.map(s=>s.y))<2,'mobile not 3 simultaneous seats');
 await page.screenshot({path:'docs/design/20261022/compact-implemented/classroom-mobile.png'});
 await page.getByRole('combobox',{name:'切换页面',exact:true}).selectOption('/courses');
 await page.waitForSelector('.course-desk');check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile horizontal overflow');
 await page.getByRole('button',{name:'组织 · 计划夹板',exact:true}).click();
 await page.screenshot({path:'docs/design/20261022/compact-implemented/course-mobile-modal.png'});await page.keyboard.press('Escape');
 await page.screenshot({path:'docs/design/20261022/compact-implemented/desk-mobile.png'});
 return {dashboards:out,desk:stage,seats,mobile};
}
