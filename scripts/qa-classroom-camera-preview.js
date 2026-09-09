// Run after qa-classroom-ui.js in the same isolated CLI browser session.
// All API writes remain blocked; video is a canvas stream, never a real device.
async page => {
  const failures=[], writes=[], errors=[];
  const check=(ok,message)=>{if(!ok) failures.push(message);};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(request.url().includes('/api/') && request.method()!=='GET') writes.push(request.url());});
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.waitForFunction(()=>window.__classroomQA?.capabilities.value);
  await page.evaluate(()=>{
    window.__previewRequests=[]; window.__previewTracks=[];
    navigator.mediaDevices.getUserMedia=async options=>{
      window.__previewRequests.push(options);
      if(window.__denyPreview) throw new DOMException('Synthetic permission rejection','NotAllowedError');
      if(!options.video || options.audio!==false) throw new Error('Preview requested microphone');
      const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;
      const ctx=canvas.getContext('2d');ctx.fillStyle='#171320';ctx.fillRect(0,0,640,360);
      ctx.fillStyle='#fff';ctx.font='24px sans-serif';ctx.fillText('Synthetic camera preview',140,180);
      const stream=canvas.captureStream(10);window.__previewTracks.push(...stream.getTracks());return stream;
    };
  });
  const open=page.getByRole('button',{name:'打开摄像头',exact:true});
  const consent=page.getByRole('checkbox',{name:'同意摄像头开启',exact:true});
  check(await open.isVisible(),'Standalone camera button must be visible before consent');
  check(await open.isDisabled(),'Preview requires camera consent');
  await consent.check();
  check(await open.isEnabled(),'Camera consent alone should enable preview');
  check(!await page.getByRole('checkbox',{name:'同意语音识别与 AI 评课',exact:true}).isChecked(),'Audio consent must remain independent');
  // Preview must also work when model services are unavailable.
  await page.evaluate(()=>{window.__classroomQA.capabilities.value.services.dialogue.configured=false;});
  check(await page.getByRole('button',{name:'开始授课',exact:true}).isDisabled(),'Unavailable classroom should remain disabled');
  await page.screenshot({path:'output/playwright/camera-open-button.png',fullPage:true});
  await open.click();
  await page.waitForFunction(()=>window.__classroomQA.cameraEnabled.value && !window.__classroomQA.busy.value);
  check(await page.getByRole('button',{name:'关闭摄像头预览',exact:true}).isVisible(),'Preview close button missing');
  check(await page.evaluate(()=>{
    const live=window.__classroomQA;
    return live.state.value==='idle' && live.room.value===null && live.elapsed.value===0 &&
      window.__previewRequests.length===1 && window.__previewRequests.every(r=>r.video && r.audio===false);
  }),'Preview must not start a lesson, microphone or clock');
  await page.getByRole('button',{name:'关闭摄像头预览',exact:true}).click();
  check(await page.evaluate(()=>window.__previewTracks.every(track=>track.readyState==='ended')),'Closing preview must stop tracks');
  await page.evaluate(()=>{window.__denyPreview=true;});
  await open.click();
  await page.getByRole('alert').filter({hasText:'摄像头不可用'}).waitFor();
  check(await open.isEnabled(),'Rejected camera permission must leave a retry button');
  await page.evaluate(()=>{window.__denyPreview=false;});
  await open.click();
  await page.waitForFunction(()=>window.__classroomQA.cameraEnabled.value && !window.__classroomQA.busy.value);
  await consent.uncheck();
  await page.waitForFunction(()=>!window.__classroomQA.cameraEnabled.value);
  check(await page.evaluate(()=>window.__previewTracks.every(track=>track.readyState==='ended')),'Withdrawing consent must stop preview');
  check(await open.isDisabled(),'Withdrawing consent must disable reopening');
  for(const width of [1440,768,320]) {
    await page.setViewportSize({width,height:900});
    check(await open.isVisible(),`Preview button hidden at ${width}`);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Horizontal overflow at ${width}`);
  }
  await page.setViewportSize({width:1440,height:1080});
  check(writes.length===0,'Preview must not make API writes');
  check(errors.length===0,`Browser errors: ${errors.join('; ')}`);
  return {result:failures.length?'FAILED':'PASSED',failures,writes,errors};
}
