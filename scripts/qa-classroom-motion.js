// Run after qa-classroom-ui.js in the SAME isolated playwright-cli session.
// Uses synthetic video + landmarks only. The existing fixture blocks device/API writes.
async (page) => {
  const failures = [], layouts = [];
  const check = (ok, message) => { if (!ok) failures.push(message); };
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.evaluate(async () => {
    const live = window.__classroomQA;
    if (!live) throw new Error('Run qa-classroom-ui.js first');
    live.room.value = { session_id: 900, state: 'active', students: {}, mode: 'full' };
    live.state.value = 'listening'; live.error.value = ''; live.events.value = [];
    live.partial.value = '同学们，分成两份就一定是平均分吗？';
    live.activeStudent.value = null; live.raised.value = 'yu'; live.playbackStudent.value = null;
    live.reply.value = { id:'qa-stream', studentId:'ming', phase:'thinking', text:'', replyId:null };
    live.cameraEnabled.value = true; live.motionStatus.value = live.handStatus.value = 'ready';
    const source = document.createElement('canvas'); source.width = 640; source.height = 480;
    const ctx = source.getContext('2d');
    ctx.fillStyle = '#16111e'; ctx.fillRect(0,0,640,480);
    ctx.strokeStyle = '#352640'; ctx.lineWidth = 1;
    for(let x=0;x<640;x+=40) { ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,480);ctx.stroke(); }
    for(let y=0;y<480;y+=40) { ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(640,y);ctx.stroke(); }
    ctx.fillStyle='#d4c4e2'; ctx.font='18px sans-serif'; ctx.fillText('本地动作可视化 · 模拟画面',24,32);
    const body = Array.from({length:33},()=>({x:.5,y:.23,visibility:0}));
    for (const [i,x,y] of [[11,.4,.35],[12,.6,.35],[13,.3,.48],[14,.7,.48],[15,.22,.28],[16,.78,.28],[23,.43,.65],[24,.57,.65],[25,.4,.8],[26,.6,.8],[27,.38,.94],[28,.62,.94]]) body[i]={x,y,visibility:.99};
    const hand = (x) => Array.from({length:21},(_,i)=>({x:x+(i===0?0:(Math.floor((i-1)/4)-2)*.018),y:i===0?.28:.24-((i-1)%4)*.03}));
    const hands = [hand(.22),hand(.78)];
    const stream = source.captureStream(10); window.__qaVideoStream = stream;
    live.camera.value.srcObject = stream; await live.camera.value.play();
    window.__qaMotionTimer = setInterval(() => { live.landmarks.value = {body,hands,at:performance.now()}; },100);
  });
  await page.locator('.student-bubble').first().waitFor();
  check(await page.locator('.student-bubble').first().innerText().then(t=>t.includes('思考中')), 'Thinking bubble missing');
  check(!await page.getByRole('checkbox',{name:'字幕',exact:true}).isChecked(), 'Captions must default off');
  await page.waitForTimeout(200);
  check(await page.getByText(/身体已捕捉 · 2 只手/).isVisible(),'Body/hands status missing');
  check(await page.locator('.motion-frame canvas').evaluate(el=>el.getContext('2d').getImageData(0,0,el.width,el.height).data.some((v,i)=>i%4===3&&v>0)), 'Skeleton canvas must contain strokes');
  await page.evaluate(() => { const r=window.__classroomQA.reply; r.value={...r.value,phase:'generating',text:'老师，我觉得'}; });
  await page.waitForTimeout(100);
  check(await page.locator('.student-bubble').first().innerText().then(t=>t.includes('老师，我觉得')), 'Draft text missing');
  await page.evaluate(() => { const r=window.__classroomQA.reply; r.value={...r.value,text:r.value.text+'两份一样大才是平均分。'}; });
  for (const width of [1440,1024,768,320]) {
    await page.setViewportSize({width,height:900});
    await page.getByRole('button',{name:'全屏放大',exact:true}).scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflow at ${width}`);
    await page.screenshot({path:`output/playwright/classroom-motion-${width}.png`,fullPage:true});
    await page.getByRole('button',{name:'全屏放大',exact:true}).click();
    check(await page.getByRole('button',{name:'退出全屏',exact:true}).isVisible(),`Fullscreen missing at ${width}`);
    await page.getByRole('checkbox',{name:'字幕',exact:true}).check();
    await page.getByRole('combobox',{name:'字幕字号'}).selectOption('36');
    check(await page.locator('.camera-captions').evaluate(el=>getComputedStyle(el).fontSize)==='36px','Large caption font not applied');
    check(await page.locator('.caption-speaker').innerText().then(t=>t.includes('小明')),'Student speaker missing');
    await page.getByRole('combobox',{name:'字幕内容'}).selectOption('teacher');
    check(!await page.locator('.camera-captions').innerText().then(t=>t.includes('小明')),'Teacher filter failed');
    check(await page.locator('.caption-speaker').innerText()==='老师','Teacher speaker missing');
    await page.getByRole('combobox',{name:'字幕内容'}).selectOption('all');
    for(const size of ['20','28','36']) { await page.getByRole('combobox',{name:'字幕字号'}).selectOption(size); check(await page.locator('.camera-captions').evaluate(el=>el.scrollHeight>=el.clientHeight),'Caption viewport invalid'); }
    const layout = await page.locator('.classroom-camera').evaluate(el=>({width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth,fullscreen:document.fullscreenElement===el}));
    layouts.push(layout); check(layout.scroll<=layout.client,`Fullscreen overflow at ${width}`);
    await page.screenshot({path:`output/playwright/classroom-fullscreen-${width}.png`});
    await page.getByRole('button',{name:'退出全屏',exact:true}).click();
    check(await page.getByRole('button',{name:'全屏放大',exact:true}).evaluate(el=>document.activeElement===el),'Focus not restored');
  }
  await page.locator('.classroom-camera').evaluate(el=>{ el.requestFullscreen=async()=>{throw new Error('Synthetic unsupported API');}; });
  await page.getByRole('button',{name:'全屏放大',exact:true}).click();
  check(await page.getByRole('dialog',{name:'老师镜头'}).isVisible(),'Fullscreen fallback missing');
  await page.getByRole('button',{name:'退出全屏',exact:true}).focus();
  await page.keyboard.press('Shift+Tab');
  check(await page.evaluate(()=>Boolean(document.activeElement.closest('.classroom-camera'))),'Fallback focus escaped');
  await page.keyboard.press('Escape');
  check(!await page.getByRole('dialog',{name:'老师镜头'}).count(),'Fallback Escape failed');
  await page.evaluate(()=>{clearInterval(window.__qaMotionTimer);});
  await page.waitForTimeout(900);
  check(await page.locator('.motion-frame canvas').evaluate(el=>!el.getContext('2d').getImageData(0,0,el.width,el.height).data.some((v,i)=>i%4===3&&v>0)),'Stale skeleton was not cleared');
  await page.evaluate(()=>{const l=window.__classroomQA;l.handStatus.value='failed';l.reply.value={...l.reply.value,phase:'failed',error:'连接中断，请重试',text:''};});
  check(await page.getByRole('button',{name:'重新加载动作模型'}).isVisible(),'Hand model retry missing');
  check(await page.getByRole('button',{name:'重新生成回复'}).isVisible(),'Generation retry missing');
  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.locator('.student-body').first().evaluate(el=>getComputedStyle(el).animationName)==='none','Reduced motion not honored');
  check(await page.evaluate(()=>window.__deviceRequests)===0,'Device access occurred');
  await page.evaluate(()=>{window.__qaVideoStream.getTracks().forEach(t=>t.stop());window.__classroomQA.cameraEnabled.value=false;window.__classroomQA.camera.value.srcObject=null;});
  return {failures,layouts,result:failures.length?'FAILED':'PASSED'};
}
