// Run after qa-classroom-ui.js in an isolated playwright-cli session.
// Same mock API fixture: no production data, no real devices, no paid services.
async page => {
  const failures=[], errors=[], requests=[];
  const check=(ok,message)=>{ if(!ok) failures.push(message); };
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{ if(request.url().includes('/api/')) requests.push({url:request.url(),method:request.method()}); });
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:1440,height:1000});
  await page.goto('http://127.0.0.1:5188/training?mode=fragment&courseId=9');
  await page.getByRole('heading',{name:'模拟课堂',exact:true}).waitFor();
  await page.waitForFunction(()=>window.__classroomQA?.capabilities.value);
  check(page.url().endsWith('/classroom?mode=fragment'),'Legacy entry must land directly on classroom');
  check(await page.locator('#class-mode').inputValue()==='fragment','Eight minute entry lost selected duration');
  check(!await page.locator('.train-setup').count(),'Legacy stage should not render');
  check(!requests.some(r=>r.url.includes('/training/')),'Legacy entry must not start or fetch old training');
  check(await page.evaluate(()=>window.__deviceRequests)===0,'Navigation must not request devices');
  check(await page.getByRole('button',{name:'打开摄像头',exact:true}).isDisabled(),'Consent must gate standalone preview');
  check(await page.locator('.class-start-feedback').evaluate(el=>el.getBoundingClientRect().height<60),'Simple consent hint should be compact');
  await page.waitForFunction(()=>[...document.querySelectorAll('.student-sprite')].every(im=>im.complete&&im.naturalWidth>0));
  check(await page.locator('.student-sprite').count()===6,'All six supplied sprites must load');
  check(await page.locator('.student-sprite.visible[src$="listening.png"]').count()===3,'Idle students must be listening');
  await page.locator('#class-mode').selectOption('full');
  await page.getByRole('slider',{name:'上课音量',exact:true}).fill('0.35');
  await page.getByRole('button',{name:'静音学生声音',exact:true}).click();
  check(await page.getByRole('slider',{name:'上课音量',exact:true}).inputValue()==='0','Mute failed');
  await page.getByRole('button',{name:'恢复学生声音',exact:true}).click();
  check(await page.getByRole('slider',{name:'上课音量',exact:true}).inputValue()==='0.35','Unmute must restore prior volume');
  await page.getByRole('button',{name:'课堂字幕',exact:true}).click();
  check(await page.getByRole('button',{name:'课堂字幕',exact:true}).getAttribute('aria-pressed')==='false','CC toggle did not turn off');
  await page.getByRole('button',{name:'课堂字幕',exact:true}).click();
  await page.getByRole('combobox',{name:'画面分辨率',exact:true}).selectOption('360');
  check(await page.evaluate(()=>window.__classroomQA.cameraResolution.value)===360,'Toolbar quality did not update');
  for(const [width,height] of [[1440,1000],[1024,900],[768,900],[320,900]]) {
    await page.setViewportSize({width,height});
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow at ${width}`);
    await page.locator('.camera-stage').scrollIntoViewIfNeeded();
    await page.screenshot({path:`output/playwright/player-ready-${width}.png`,fullPage:true});
    await page.getByRole('button',{name:'全屏放大',exact:true}).click();
    check(await page.locator('.classroom-camera').evaluate(el=>document.fullscreenElement===el),'Native fullscreen should be used when available');
    await page.getByRole('button',{name:'课堂设置',exact:true}).click();
    await page.keyboard.press('Tab');
    check(await page.evaluate(()=>!!document.activeElement.closest('dialog[open]')),'Dialog focus escaped');
    await page.keyboard.press('Escape');
    check(await page.getByRole('button',{name:'退出全屏',exact:true}).isVisible(),'Escape should close settings, not fullscreen');
    const frame=await page.locator('.motion-frame').boundingBox();
    for(const phase of ['thinking','generating','playing','done']) {
      await page.evaluate(phase=>{
        const live=window.__classroomQA;
        live.reply.value={id:'player-sprite-qa',studentId:'ming',replyId:'sprite-r',phase,text:phase==='thinking'?'':'老师，平均分就是每份一样大。'.repeat(phase==='generating'?8:1)};
        live.playbackStudent.value=phase==='playing'?'ming':null;
      },phase);
      await page.waitForTimeout(100);
      const next=await page.locator('.motion-frame').boundingBox();
      check(Math.abs(frame.height-next.height)<1,`Frame shifted during ${phase} at ${width}`);
      const pose=phase==='done'?'listening':'raised';
      check(await page.locator(`.student-sprite.visible[src$="ming-${pose}.png"]`).count()===1,`Wrong sprite for ${phase}`);
    }
    for(const button of await page.locator('.player-icon-button:not(:disabled)').all()) {
      await button.focus();
      check(await page.locator('.classroom-camera').evaluate(el=>el.scrollWidth<=el.clientWidth),`Tooltip overflow at ${width}`);
    }
    check(await page.locator('.fullscreen-students').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight),`Students clipped at ${width}`);
    await page.screenshot({path:`output/playwright/player-fullscreen-${width}.png`});
    await page.getByRole('button',{name:'退出全屏',exact:true}).click();
    await page.evaluate(()=>{const l=window.__classroomQA;l.reply.value={phase:'idle'};l.playbackStudent.value=null;});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.evaluate(()=>{
    const l=window.__classroomQA;
    l.reply.value={id:'final-preview',studentId:'ming',phase:'generating',text:'老师，每份一样大才是平均分，对吗？'};
    l.raised.value='yu';
  });
  await page.locator('.camera-stage').scrollIntoViewIfNeeded();
  await page.locator('.classroom-heading h1').click();
  await page.waitForTimeout(600); // Let the click feedback and sprite entry animation settle for the preview.
  await page.screenshot({path:'output/playwright/classroom-player-final.png',fullPage:true});
  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.locator('.student-sprite.visible').first().evaluate(el=>getComputedStyle(el).animationName)==='none','Reduced motion failed');
  check(!requests.some(r=>r.method!=='GET'),'No API writes expected');
  check(errors.length===0,errors.join('; '));
  return {result:failures.length?'FAILED':'PASSED',failures,errors};
}
