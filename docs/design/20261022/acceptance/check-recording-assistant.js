async (page) => {
  const check=(value,message)=>{if(!value)throw new Error(message);};
  await page.reload();await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'对话布局',exact:true}).click();
  await page.getByRole('button',{name:'合成课堂录像 10 秒',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.motion-frame video')?.srcObject?.active);
  const video=await page.locator('.motion-frame video').elementHandle();
  const ids=await video.evaluate(el=>el.srcObject.getTracks().map(t=>t.id).join(','));
  const stage=await page.locator('.student-stage canvas').elementHandle();
  for(let i=0;i<3;i++){
    await page.getByRole('button',{name:'默认布局',exact:true}).click();
    await page.getByRole('button',{name:'对话布局',exact:true}).click();
  }
  check(await video.evaluate(el=>el===document.querySelector('.motion-frame video')&&el.srcObject.active),'recording video remounted or stopped');
  check(ids===await video.evaluate(el=>el.srcObject.getTracks().map(t=>t.id).join(',')),'media tracks replaced');
  check(await stage.evaluate(el=>el===document.querySelector('.student-stage canvas')),'pixel canvas replaced');
  await page.waitForFunction(()=>document.querySelector('[data-testid="fixture-result"]')?.textContent.includes('recordedBytes'));
  const result=JSON.parse(await page.locator('[data-testid="fixture-result"]').textContent());
  check(result.recordedBytes>1000&&result.audioTracks===1&&result.studentFrames>0,'recording missing video, audio or student frames');
  const replay=page.getByLabel('本机录像回放');
  await replay.evaluate(async video=>{await video.play();});
  await page.waitForFunction(()=>document.querySelector('.fixture-preview video')?.currentTime>.1);
  await replay.evaluate(video=>video.pause());
  const assistant=page.getByRole('button',{name:'打开 阿贝贝老师，可拖动调整位置'});
  await assistant.click();
  check(await page.locator('.help-chat').isVisible(),'assistant chat did not open');
  await page.locator('.help-chat .close-x').click();
  const before=await assistant.boundingBox();
  await page.mouse.move(before.x+before.width/2,before.y+before.height/2);await page.mouse.down();
  await page.mouse.move(before.x-160,before.y-120,{steps:10});await page.mouse.up();
  const after=await assistant.boundingBox();check(after.x<before.x-50,'assistant dragging failed');
  check(await page.locator('.digital-human canvas').evaluate(canvas=>!!canvas.getContext('2d')),'assistant is not Canvas 2D');
  return {recording:result,checks:'same camera stream and student canvas during layout switches; playable recording; pixel assistant opens chat and drags'};
}
