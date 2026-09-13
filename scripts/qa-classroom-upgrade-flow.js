// Isolated full UI flow with synthetic devices, mock REST/WS and real MediaRecorder.
async page => {
  const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const native=window.WebSocket;
    window.WebSocket=class {
      static OPEN=1;
      constructor(url){if(!url.includes('/api/classroom/live'))return new native(url);
        this.readyState=1;this.bufferedAmount=0;this.seq=0;window.__mockClassSocket=this;setTimeout(()=>this.onopen?.(),30);}
      send(raw){const m=JSON.parse(raw);if(m.ticket){this.emit('connected',{students:[{id:'ming',name:'小明'},{id:'yu',name:'小雨'},{id:'lin',name:'小林'}],elapsed:15,wall_elapsed:15});this.emit('ready');}}
      emit(type,data={}){this.onmessage?.({data:JSON.stringify({type,session_id:9902,seq:++this.seq,at_ms:15000,...data})});}
      close(){this.readyState=3;this.onclose?.();}
    };
    window.Worker=class {postMessage(m){if(m.type==='init')setTimeout(()=>this.onmessage?.({data:{type:'ready'}}),10);}terminate(){}};
    navigator.mediaDevices.getUserMedia=async options=>{
      if(options.video){const c=document.createElement('canvas');c.width=640;c.height=360;const x=c.getContext('2d');
        const draw=()=>{x.fillStyle='#294968';x.fillRect(0,0,640,360);x.fillStyle='#fff';x.font='24px sans-serif';x.fillText('SYNTHETIC CLASSROOM',40,180);};draw();
        const timer=setInterval(draw,100);const stream=c.captureStream(24);stream.getVideoTracks()[0].addEventListener('ended',()=>clearInterval(timer));return stream;}
      const c=new AudioContext();await c.resume();const o=c.createOscillator(),g=c.createGain(),d=c.createMediaStreamDestination();g.gain.value=.05;o.connect(g);g.connect(d);o.start();return d.stream;
    };
  });
  let lessonState='active';
  const room=()=>({session_id:9902,state:lessonState,mode:'full',topic:'合成课堂',elapsed:15,active_elapsed:15,wall_elapsed:15,
    events:[],students:{},report_state:lessonState==='ended'?'insufficient':'idle',report_readiness:{reasons:['合成测试，无真实授课证据']}});
  await page.route('**/api/classroom/sessions**',async route=>{
    const path=route.request().url().replace(/^https?:\/\/[^/]+/,'').split('?')[0],method=route.request().method();
    if(method==='POST')writes.push(path);
    if(path.endsWith('/ticket'))return route.fulfill({json:{ticket:'synthetic'}});
    if(path.endsWith('/pause'))lessonState='paused';
    if(path.endsWith('/resume'))lessonState='active';
    if(path.endsWith('/finish')){lessonState='ended';await page.evaluate(()=>window.__mockClassSocket?.emit('ended'));}
    return route.fulfill({json:path==='/api/classroom/sessions' && method==='GET'?{items:[]}:room()});
  });
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.getByRole('heading',{name:'模拟课堂',exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'同意语音识别与 AI 评课'}).check();
  await page.getByRole('checkbox',{name:'同意摄像头开启'}).check();
  await page.getByRole('checkbox',{name:'本机录像',exact:true}).check();
  await page.getByRole('button',{name:'打开摄像头',exact:true}).click();
  await page.getByRole('region',{name:'开课取景校准'}).waitFor();
  await page.getByRole('region',{name:'开课取景校准'}).getByRole('button',{name:'继续',exact:true}).click();
  await page.getByRole('button',{name:'开始授课',exact:true}).click();
  await page.getByText('录像 · 录制中',{exact:false}).waitFor();
  await page.waitForTimeout(800);
  await page.getByRole('button',{name:'暂停课堂',exact:true}).click();
  await page.getByRole('button',{name:'继续授课',exact:true}).waitFor();
  await page.waitForFunction(()=>window.__classroomQA.room.value.state==='paused');
  const elapsed=await page.evaluate(()=>window.__classroomQA.elapsed.value);
  await page.waitForTimeout(700);
  if(await page.evaluate(()=>window.__classroomQA.elapsed.value)!==elapsed)throw new Error('Paused clock still advances');
  await page.getByRole('button',{name:'继续授课',exact:true}).click();
  await page.getByText('录像 · 录制中',{exact:false}).waitFor();
  await page.waitForTimeout(800);
  await page.getByRole('button',{name:'结束并评课',exact:true}).click();
  await page.getByRole('dialog',{name:'课后录像预览'}).waitFor();
  if(!await page.getByRole('button',{name:'保存到本机',exact:true}).isVisible())throw new Error('Save choice absent');
  await page.getByRole('button',{name:'保存到本机',exact:true}).click();
  await page.getByRole('button',{name:'已保存到本机',exact:true}).waitFor();
  await page.getByRole('dialog',{name:'课后录像预览'}).locator('video').evaluate(async video=>{await video.play();await new Promise(resolve=>setTimeout(resolve,200));video.pause();});
  await page.screenshot({path:'output/playwright/classroom-recording-preview.png',fullPage:true});
  await page.getByRole('button',{name:'关闭课后录像预览',exact:true}).click();
  await page.getByRole('link',{name:'查看 AI 评课 ↗'}).click();
  await page.getByRole('button',{name:'录像与课堂记录',exact:true}).click();
  await page.getByRole('dialog',{name:'录像与课堂记录'}).locator('video').waitFor();
  await page.getByRole('dialog',{name:'录像与课堂记录'}).locator('video').evaluate(async video=>{await video.play();await new Promise(resolve=>setTimeout(resolve,200));video.pause();});
  await page.screenshot({path:'output/playwright/classroom-recording-review.png',fullPage:true});
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:/下载本节录像/}).click();
  await (await download).saveAs('output/playwright/classroom-ui-recording.webm');
  await page.getByText('管理本机录像（1）',{exact:true}).click();
  page.removeAllListeners('dialog');page.on('dialog',dialog=>dialog.accept());
  await page.locator('.classroom-replay li').filter({hasText:'课堂 #9902'}).getByRole('button',{name:'删除',exact:true}).click();
  await page.getByText('当前浏览器没有本节录像。换设备或清理浏览器数据后，录像不会自动恢复。',{exact:true}).waitFor();
  return {result:errors.length?'FAILED':'PASSED',errors,writes,downloaded:true,deletedSyntheticRecording:true};
}
