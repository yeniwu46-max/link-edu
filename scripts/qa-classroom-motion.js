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
    live.cameraEnabled.value = true; live.motionStatus.value = live.handStatus.value = live.faceStatus.value = 'ready';
    live.pose.value = {motion_version:2, body:{status:'observed',scope:'torso',left_raised:true},
      hands:{status:'observed',gestures:[{label:'Open_Palm',score:.95}]},
      face:{status:'observed',nose_offset_ratio:.1}};
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
    const face = Array.from({length:478},(_,i)=>({x:.5+.06*Math.cos(i*.4),y:.22+.07*Math.sin(i*.4)}));
    const stream = source.captureStream(10); window.__qaVideoStream = stream;
    live.camera.value.srcObject = stream; await live.camera.value.play();
    window.__qaMotionTimer = setInterval(() => { live.landmarks.value = {body,hands,face,at:performance.now()}; },100);
  });
  await page.locator('.student-bubble').first().waitFor();
  check(await page.locator('.student-bubble').first().innerText().then(t=>t.includes('思考中')), 'Thinking bubble missing');
  check(await page.locator('.camera-captions').isVisible(), 'Captions must default on in primary camera');
  await page.waitForTimeout(200);
  check((await page.locator('.motion-statusbar').innerText()).includes('身体已捕捉 · 2 只手'),'Body/hands status missing');
  check((await page.locator('.motion-statusbar').innerText()).includes('面部已捕捉'),'Face status missing');
  check(await page.locator('.student-attention').count()===2,'Thinking and question exclamation marks missing');
  check(await page.locator('.motion-observations').innerText().then(t=>t.includes('手掌展开')&&t.includes('面部大致朝向镜头')),'Motion features missing');
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
    await page.getByRole('button',{name:'课堂记录',exact:true}).click();
    await page.keyboard.press('Escape');
    const recordsOpen=await page.getByRole('dialog',{name:'课堂记录',exact:true}).isVisible();
    const stillFullscreen=await page.getByRole('button',{name:'退出全屏',exact:true}).isVisible();
    check(!recordsOpen && stillFullscreen,`Closing records should not exit fullscreen at ${width}`);
    if(recordsOpen) await page.getByRole('button',{name:'关闭课堂记录',exact:true}).click();
    if(!stillFullscreen) await page.getByRole('button',{name:'全屏放大',exact:true}).click();
    check(await page.locator('.fullscreen-students .student-card').count()===3,`Fullscreen must include three students at ${width}`);
    await page.getByRole('button',{name:'课堂设置',exact:true}).click();
    check(await page.getByRole('combobox',{name:'画面分辨率'}).count()===1,'Resolution selector missing');
    check(await page.getByRole('slider',{name:'上课音量'}).count()===1,'Lesson volume missing');
    await page.getByRole('checkbox',{name:'字幕',exact:true}).check();
    await page.getByRole('combobox',{name:'字幕字号'}).selectOption('36');
    check(await page.locator('.camera-captions').evaluate(el=>getComputedStyle(el).fontSize)==='36px','Large caption font not applied');
    check(await page.locator('.caption-lines').evaluate(el=>getComputedStyle(el).textAlign)==='center','Captions must be centered');
    check(await page.locator('.caption-speaker').innerText().then(t=>t.includes('小明')),'Student speaker missing');
    await page.getByRole('combobox',{name:'字幕内容'}).selectOption('teacher');
    check(!await page.locator('.camera-captions').innerText().then(t=>t.includes('小明')),'Teacher filter failed');
    check(await page.locator('.caption-speaker').innerText()==='老师','Teacher speaker missing');
    await page.getByRole('combobox',{name:'字幕内容'}).selectOption('all');
    for(const size of ['20','28','36']) { await page.getByRole('combobox',{name:'字幕字号'}).selectOption(size); check(await page.locator('.camera-captions').evaluate(el=>el.scrollHeight>=el.clientHeight),'Caption viewport invalid'); }
    await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
    const layout = await page.locator('.classroom-camera').evaluate(el=>({width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth,fullscreen:document.fullscreenElement===el}));
    layouts.push(layout); check(layout.scroll<=layout.client,`Fullscreen overflow at ${width}`);
    const sizes=[];
    for(let i=0;i<4;i++) {
      await page.evaluate(i=>{const l=window.__classroomQA; l.pose.value=i%2?{motion_version:2,body:{status:'observed',scope:'torso',left_raised:true},hands:{gestures:[{label:'Open_Palm'}]},face:{status:'observed',nose_offset_ratio:0}}:null;
        l.reply.value={...l.reply.value,phase:['idle','thinking','generating','done'][i],studentId:i===1?null:'ming',text:'老师，我觉得'+ '必须平均分才是一半。'.repeat(i+1)};},i);
      await page.waitForTimeout(120);
      sizes.push(await page.locator('.motion-frame').evaluate(el=>el.getBoundingClientRect().height));
    }
    check(Math.max(...sizes)-Math.min(...sizes)<=1,`Video area jumps as motion/stream text changes at ${width}: ${sizes}`);
    await page.screenshot({path:`output/playwright/classroom-fullscreen-${width}.png`});
    await page.getByRole('button',{name:'退出全屏',exact:true}).click();
    check(await page.getByRole('button',{name:'全屏放大',exact:true}).evaluate(el=>document.activeElement===el),'Focus not restored');
  }
  await page.locator('.classroom-camera').evaluate(el=>{ el.requestFullscreen=async()=>{throw new Error('Synthetic unsupported API');}; });
  await page.getByRole('button',{name:'全屏放大',exact:true}).click();
  check(await page.getByRole('dialog',{name:'老师镜头'}).isVisible(),'Fullscreen fallback missing');
  const fallbackBox=await page.locator('.classroom-camera').evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,vw:innerWidth,vh:innerHeight};});
  check(Math.abs(fallbackBox.x)<1&&Math.abs(fallbackBox.y)<1&&Math.abs(fallbackBox.width-fallbackBox.vw)<1&&Math.abs(fallbackBox.height-fallbackBox.vh)<1,`Fallback must fill viewport: ${JSON.stringify(fallbackBox)}`);
  await page.getByRole('button',{name:'退出全屏',exact:true}).focus();
  await page.keyboard.press('Shift+Tab');
  check(await page.evaluate(()=>Boolean(document.activeElement.closest('.classroom-camera'))),'Fallback focus escaped');
  await page.keyboard.press('Escape');
  check(!await page.getByRole('dialog',{name:'老师镜头'}).count(),'Fallback Escape failed');
  await page.evaluate(()=>{clearInterval(window.__qaMotionTimer);});
  await page.waitForTimeout(900);
  check(await page.locator('.motion-frame canvas').evaluate(el=>!el.getContext('2d').getImageData(0,0,el.width,el.height).data.some((v,i)=>i%4===3&&v>0)),'Stale skeleton was not cleared');
  await page.evaluate(()=>{const l=window.__classroomQA;l.faceStatus.value='failed';l.reply.value={...l.reply.value,phase:'failed',error:'连接中断，请重试',text:''};});
  check(await page.getByRole('button',{name:'重试学生回答'}).isVisible(),'Generation retry missing');
  await page.getByRole('button',{name:'课堂设置',exact:true}).click();
  check(await page.getByRole('button',{name:'重新加载动作模型'}).isVisible(),'Face model retry missing');
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.locator('.student-body').first().evaluate(el=>getComputedStyle(el).animationName)==='none','Reduced motion not honored');
  check(await page.evaluate(()=>window.__deviceRequests)===0,'Device access occurred');
  await page.evaluate(()=>{window.__qaVideoStream.getTracks().forEach(t=>t.stop());window.__classroomQA.cameraEnabled.value=false;window.__classroomQA.camera.value.srcObject=null;});
  await page.evaluate(()=>{
    const l=window.__classroomQA;l.state.value='ended';l.events.value=[{id:101,type:'pose',at_ms:2000,data:l.pose.value}];
    l.room.value={session_id:900,state:'ended',events:l.events.value,report_state:'completed',report_version:1,report:{overall_score:72,coverage:'1/6',sources:[],
      dimensions:[{key:'posture',label:'教态与站位',score:72,reason:'合成展示：手势需结合示范语境审阅。',event_ids:[101],source_ids:[]}],
      motion_evidence:{status:'observed',sample_count:10,observed_samples:8,modalities:{body:{observed_samples:8,total_samples:10},hands:{observed_samples:6,total_samples:10},face:{observed_samples:7,total_samples:10}},
        observations:[{code:'hand_open_palm',description:'手掌展开',matched_samples:4,observed_samples:6,longest_observed_span_ms:4200,suggestion:'结合对应讲解核对是否辅助示范，不按次数加分。',event_ids:[101]}],
        limitations:['样本比例不是整堂课时长占比。']}}};
  });
  await page.getByText(/教态动作证据 · 身体/).click();
  check(await page.getByText('样本比例不是整堂课时长占比。',{exact:true}).isVisible(),'Evidence limitations missing');
  await page.getByRole('button',{name:'↗ 0:02',exact:true}).last().click();
  check(await page.locator('#evidence-101').isVisible(),'Motion citation jump failed');
  await page.getByRole('button',{name:'关闭课堂记录',exact:true}).click();
  await page.setViewportSize({width:1440,height:1080});
  await page.getByRole('heading',{name:'课堂评课',exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:'output/playwright/classroom-motion-report.png',fullPage:true});
  return {failures,layouts,result:failures.length?'FAILED':'PASSED'};
}
