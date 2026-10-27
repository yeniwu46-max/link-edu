async(page)=>{
 const check=(x,m)=>{if(!x)throw Error(m)};
 await page.goto('http://127.0.0.1:5188/tests/model-pages-browser.html?page=/courses');
 await page.setViewportSize({width:1366,height:768});await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('studio');
 await page.getByRole('button',{name:'导入 · 邀请函',exact:true}).click();
 for(let i=0;i<12;i++){await page.keyboard.press('Tab');check(await page.evaluate(()=>!!document.activeElement.closest('dialog')),'focus leak');}
 await page.mouse.click(240,740);check(await page.locator('dialog[open]').count()===0,'backdrop did not close');
 await page.evaluate(()=>{const f=window.__studioFixture;f.setCourses([{id:42,title:'讲解技能',stage:'专项04',status:'in_progress',progress_percent:70,lesson_count:3,description:'长介绍'.repeat(2000)}]);return f.router.push('/resources')});
 await page.getByRole('link',{name:'课程中心',exact:true}).click();
 // Course pages are kept alive per version; navigate with an explicit new route to reload data.
 await page.evaluate(()=>window.__studioFixture.router.push('/courses?courseId=42'));
 await page.waitForSelector('dialog[open]');
 const body=page.locator('.course-modal__body');
 check(await body.evaluate(e=>e.scrollHeight>e.clientHeight),'long content not internally scrollable');
 check(await page.getByRole('button',{name:'开始训练 ↗',exact:true}).isVisible(),'start clipped');
 await page.keyboard.press('Escape');
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('original');await page.waitForSelector('.featured-row');
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('studio');
 await page.route('**/assets/desk/prep-desk.png',r=>r.abort());await page.reload();await page.waitForSelector('.course-desk--fallback');
 await page.getByRole('button',{name:'变化 · 彩色纸扇',exact:true}).click();check(await page.locator('dialog[open]').count()===1,'image fallback unusable');
 await page.keyboard.press('Escape');await page.unroute('**/assets/desk/prep-desk.png');await page.reload();
 await page.getByRole('button',{name:'打开 阿贝贝老师，可拖动调整位置'}).click();
 await page.getByRole('button',{name:'冷静',exact:true}).click();check(await page.evaluate(()=>JSON.parse(localStorage.link_settings).assistantStyle)==='calm','style not saved');
 await page.reload();await page.getByRole('button',{name:'打开 阿贝贝老师，可拖动调整位置'}).click();
 check(await page.getByRole('button',{name:'冷静',exact:true}).getAttribute('aria-pressed')==='true','style not restored');
 await page.getByRole('button',{name:'温暖',exact:true}).click();
 await page.screenshot({path:'docs/design/20261022/compact-implemented/abebei-teacher.png'});
 return 'Passed modal focus/backdrop/long body, original UI, image failure directory, assistant preference';
}
