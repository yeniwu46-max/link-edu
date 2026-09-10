// Run after qa-classroom-ui.js in the same isolated CLI browser session.
// Real Vue/WebAudio, mocked classroom WebSocket/ASR/TTS; synthetic silent tracks only.
async page => {
  const failures=[], errors=[];
  const check=(ok,message)=>{if(!ok) failures.push(message);};
  page.on('pageerror',e=>errors.push(e.message));
  const room={session_id:901,state:'active',events:[],students:{},elapsed:0,mode:'full',cloud_vision:false};
  await page.route('**/api/classroom/sessions',route=>route.request().method()==='POST'?route.fulfill({json:room}):route.fallback());
  await page.route('**/api/classroom/sessions/901',route=>route.fulfill({json:room}));
  await page.route('**/api/classroom/sessions/901/ticket',route=>route.fulfill({json:{ticket:'synthetic-only'}}));
  await page.addInitScript(()=>{
    const RealSocket=window.WebSocket;
    window.__syntheticMessages=[];
    class ClassroomSocket {
      static OPEN=1;
      constructor(url) {
        if(!url.includes('/api/classroom/live')) return new RealSocket(url);
        this.readyState=1;this.bufferedAmount=0;this.seq=0;window.__qaSocket=this;
        setTimeout(()=>this.onopen?.(),30);
      }
      emit(type,fields={}) {this.onmessage?.({data:JSON.stringify({type,session_id:901,seq:++this.seq,...fields})});}
      send(raw) {
        const m=JSON.parse(raw);if(m.type!=='audio') window.__syntheticMessages.push(m);
        if(m.ticket) {this.emit('connected',{students:[{id:'ming',name:'小明'},{id:'yu',name:'小雨'},{id:'lin',name:'小林'}],elapsed:0});this.emit('ready');}
        if(m.type==='playback_done') this.emit('listening');
      }
      close(){this.readyState=3;this.onclose?.();}
    }
    window.WebSocket=ClassroomSocket;
    navigator.mediaDevices.getUserMedia=async options=>{
      if(options.video) {
        const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;
        const ctx=canvas.getContext('2d');ctx.fillStyle='#171320';ctx.fillRect(0,0,640,360);
        return canvas.captureStream(10);
      }
      const ctx=new AudioContext();window.__syntheticInput=ctx;
      return ctx.createMediaStreamDestination().stream;
    };
  });
  await page.clock.install();
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.getByRole('heading',{name:'模拟课堂',exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'同意语音识别与 AI 评课'}).check();
  await page.getByRole('checkbox',{name:'同意摄像头开启'}).check();
  // Explicitly mute before testing real PCM scheduling; no sound sent to the user.
  await page.getByRole('button',{name:'课堂设置',exact:true}).click();
  await page.getByRole('slider',{name:'设置上课音量',exact:true}).fill('0');
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  await page.getByRole('button',{name:'开始授课',exact:true}).click();
  await page.waitForFunction(()=>window.__classroomQA?.state.value==='listening');
  check(await page.evaluate(()=>window.__classroomQA.cameraEnabled.value),'Start must open required camera');
  check(await page.getByRole('button',{name:'结束并评课',exact:true}).isDisabled(),'Finish must be locked before 10s');
  await page.getByRole('button',{name:'全屏放大',exact:true}).click();
  await page.getByRole('button',{name:'课堂设置',exact:true}).click();
  await page.getByRole('checkbox',{name:'字幕',exact:true}).check();
  await page.getByRole('combobox',{name:'字幕内容'}).selectOption('teacher');
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  await page.evaluate(()=>{
    const s=window.__qaSocket;
    s.emit('partial',{text:'小林，什么是平均分？'});
    s.emit('generation_started',{generation_id:'qa-g',student_id:'lin'});
    s.emit('reply_delta',{generation_id:'qa-g',student_id:'lin',delta:'老师，'});
  });
  const bubble=page.locator('.fullscreen-students .student-bubble');
  await bubble.waitFor();
  check((await bubble.innerText()).includes('老师，'),'First streamed text missing in fullscreen');
  await page.evaluate(()=>window.__qaSocket.emit('reply_delta',{generation_id:'qa-g',student_id:'lin',delta:'每份一样大才是平均分。'}));
  check((await bubble.innerText()).includes('每份一样大'),'Second streamed text missing');
  check(await page.locator('.fullscreen-students .student-card').count()===3,'Three fullscreen students missing');
  check((await page.locator('.caption-lines').innerText()).includes('小林，什么是平均分'),'Teacher transcript missing');
  await page.getByRole('button',{name:'课堂设置',exact:true}).click();
  await page.getByRole('combobox',{name:'字幕字号'}).selectOption('28');
  await page.getByRole('button',{name:'缩小字幕',exact:true}).click();
  check(await page.getByRole('combobox',{name:'字幕字号'}).inputValue()==='20','Shrink did not reduce font');
  check(await page.getByRole('combobox',{name:'字幕宽度'}).inputValue()==='60','Shrink did not narrow captions');
  for(const value of ['1020','720','360']) {
    await page.getByRole('combobox',{name:'设置画面分辨率',exact:true}).selectOption(value);
    await page.waitForFunction(v=>window.__classroomQA.cameraResolution.value===Number(v),value);
  }
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  await page.evaluate(()=>{
    const s=window.__qaSocket,text='老师，每份一样大才是平均分。';
    s.emit('generation_completed',{generation_id:'qa-g',student_id:'lin',text});
    s.emit('reply',{generation_id:'qa-g',student_id:'lin',reply_id:'qa-r',text});
    s.emit('audio',{reply_id:'qa-r',sample_rate:24000,audio:btoa('\0'.repeat(24000))});
    s.emit('audio_end',{reply_id:'qa-r',ok:true});
  });
  await page.waitForFunction(()=>window.__classroomQA.playbackStudent.value==='lin');
  check(await page.locator('.fullscreen-students .student-card.speaking').count()===1,'Playback did not animate the named student');
  await page.waitForFunction(()=>window.__syntheticMessages.some(m=>m.type==='playback_done'));
  check(await page.evaluate(()=>window.__classroomQA.state.value)==='listening','Playback completion did not restore listening');
  check(await page.evaluate(()=>window.__syntheticMessages.some(m=>m.type==='playback_started')),'Playback start acknowledgment missing');
  await page.getByRole('button',{name:'课堂设置',exact:true}).click();
  await page.getByRole('slider',{name:'设置上课音量',exact:true}).fill('0.35');
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  check(await page.evaluate(()=>window.__classroomQA.volume.value)===.35,'Volume control not connected');
  await page.setViewportSize({width:844,height:390});
  const layout=await page.locator('.classroom-camera').evaluate(el=>({height:innerHeight,scroll:el.scrollHeight,client:el.clientHeight,
    video:el.querySelector('.motion-frame').getBoundingClientRect().height,bottom:el.querySelector('.fullscreen-students').getBoundingClientRect().bottom}));
  check(layout.video>30&&layout.bottom<=layout.height+1&&layout.scroll<=layout.client,'Landscape fullscreen clips camera or students');
  check(await page.locator('.camera-captions').evaluate(el=>{const r=el.getBoundingClientRect(),p=el.parentElement.getBoundingClientRect();return r.top>=p.top&&r.bottom<=p.bottom;}),'Landscape captions escape camera frame');
  await page.screenshot({path:'output/playwright/classroom-fullscreen-landscape.png'});
  await page.getByRole('button',{name:'退出全屏',exact:true}).click();
  // Accelerated presentation-only clock verifies 15s retention without real devices or paid calls.
  await page.evaluate(()=>{const r=window.__classroomQA.reply;r.value={...r.value,id:'qa-retention',action:'followup',phase:'done',text:'老师，为什么要平均分？'};});
  await page.waitForFunction(()=>document.querySelector('.student-bubble')?.textContent.includes('为什么要平均分'));
  await page.clock.fastForward(14000);
  check(await bubble.isVisible(),'Question must remain for at least 10 seconds');
  await page.clock.fastForward(1500);
  await bubble.waitFor({state:'detached'}); // Vue's short leave transition follows the 15s retention timer.
  check(await bubble.count()===0,'Question bubble must disappear after 15 seconds');
  check(await page.getByRole('button',{name:'结束并评课',exact:true}).isEnabled(),'Finish must unlock after 10 seconds');
  await page.getByRole('button',{name:'暂停设备采集',exact:true}).click();
  check(!await page.evaluate(()=>window.__classroomQA.cameraEnabled.value),'Pause must release camera');
  await page.evaluate(async()=>{window.__qaSocket.close();await window.__syntheticInput.close();});
  check(errors.length===0,errors.join('; '));
  return {result:failures.length?'FAILED':'PASSED',failures,errors,layout};
}
