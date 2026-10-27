async(page)=>{
 const check=(v,m)=>{if(!v)throw Error(m)};
 await page.goto('http://127.0.0.1:5188/tests/model-pages-browser.html?page=/classroom');
 await page.getByRole('combobox',{name:'UI 版本',exact:true}).selectOption('studio');
 await page.getByRole('button',{name:'对话布局',exact:true}).click();await page.waitForSelector('.student-stage[data-renderer="ready"]');
 const out=[];
 for(const theme of ['classic','academy'])for(const [width,height] of [[1280,720],[1366,768],[1440,900],[390,844]]){
   await page.setViewportSize({width,height});await page.getByRole('combobox',{name:'界面风格',exact:true}).selectOption(theme);
   await page.getByRole('button',{name:'复位教师小窗位置',exact:true}).click();
   const m=await page.evaluate(()=>{let rect=s=>{let r=document.querySelector(s).getBoundingClientRect();return{top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height}};return{bar:rect('.player-console'),camera:rect('.motion-frame'),students:rect('.fullscreen-students'),seats:[...document.querySelectorAll('[data-student-viewport]')].map(e=>{let r=e.getBoundingClientRect();return{height:r.height,bottom:r.bottom}}),scroll:document.querySelector('.classroom-page').scrollHeight,client:document.querySelector('.classroom-page').clientHeight}});
   check(m.seats.length===3&&m.seats.every(s=>s.height>=50&&s.bottom<m.bar.top),'seat or bar clipped '+JSON.stringify(m));check(m.bar.bottom<=height,'controls outside viewport');
   if(width<700)check(m.camera.top>=m.students.bottom,'camera hides student');
   out.push({theme,width,height,...m});
   await page.screenshot({path:'docs/design/20261022/compact-implemented/classroom-'+theme+'-'+width+'.png'});
 }
 return out
}
