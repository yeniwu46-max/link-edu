// Run after qa-classroom-ui.js. All APIs mocked; only synthetic canvas and tones.
async page => {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.getByRole('heading',{name:'模拟课堂',exact:true}).waitFor();
  if(await page.getByRole('checkbox',{name:'本机录像',exact:true}).isChecked())throw new Error('Recording must be opt-in');
  await page.getByRole('checkbox',{name:'本机录像',exact:true}).check();
  const media=await page.evaluate(async()=>{
    const {ClassroomRecorder}=await import('/src/services/classroomRecorder.js');
    const {ClassroomAudio}=await import('/src/services/classroomAudio.js');
    const store=await import('/src/services/classroomRecordingStore.js');
    const wait=ms=>new Promise(r=>setTimeout(r,ms));
    const synthetic=new AudioContext();await synthetic.resume();
    const teacher=synthetic.createOscillator(), teacherGain=synthetic.createGain(),dest=synthetic.createMediaStreamDestination();
    teacher.frequency.value=440;teacherGain.gain.value=.12;teacher.connect(teacherGain);teacherGain.connect(dest);teacher.start();
    const old=navigator.mediaDevices.getUserMedia;navigator.mediaDevices.getUserMedia=async()=>dest.stream;
    const messages=[];const audio=new ClassroomAudio((type,data)=>messages.push({type,...data}),()=>{});
    await audio.start();navigator.mediaDevices.getUserMedia=old;
    const base=performance.now(),paint={bright:false};let resolve,error='';
    const done=new Promise(r=>{resolve=r;});
    const rec=new ClassroomRecorder({paint:(ctx,c)=>{ctx.fillStyle=paint.after?'#ff0000':paint.bright?'#ffffff':'#000000';ctx.fillRect(0,0,c.width,c.height);},
      getWallMs:()=>performance.now()-base,getAudioStream:()=>audio.recordingStream(),onResult:resolve,onError:e=>{error=e;},onState:()=>{}});
    await rec.start();await wait(350);
    const pcm=new Int16Array(24000);for(let i=0;i<pcm.length;i++)pcm[i]=Math.round(Math.sin(i*2*Math.PI*880/24000)*8000);
    let binary='';for(const byte of new Uint8Array(pcm.buffer))binary+=String.fromCharCode(byte);
    const marker=performance.now()-base;paint.bright=true;
    audio.chunk('synth',btoa(binary),24000);audio.end('synth',true);
    await wait(1050);rec.pause();const gapStart=performance.now()-base;await wait(650);
    paint.after=true;await rec.resume();await wait(500);rec.stop();
    const result=await Promise.race([done,wait(5000).then(()=>{throw new Error('Recorder did not finish');})]);
    if(error)throw new Error(error);
    if(store.recordingTime(result.segments,gapStart+300)!==null)throw new Error('Pause mapped to unrelated video');
    await store.saveClassroomRecording(location.origin,1,9901,result.blob,{segments:result.segments,filename:'synthetic.webm'});
    if(await store.getClassroomRecording(location.origin,2,9901))throw new Error('Cross-account recording leak');
    const read=await store.getClassroomRecording(location.origin,1,9901);
    if(read.blob.size!==result.blob.size)throw new Error('Stored recording corrupt');
    const decoded=await synthetic.decodeAudioData(await result.blob.arrayBuffer());
    const samples=decoded.getChannelData(0),sr=decoded.sampleRate;
    const energy=(freq,start,end)=>{let a=0,b=0;const lo=Math.floor(start*sr),hi=Math.min(samples.length,Math.floor(end*sr));
      for(let i=lo;i<hi;i++){a+=samples[i]*Math.cos(2*Math.PI*freq*i/sr);b+=samples[i]*Math.sin(2*Math.PI*freq*i/sr);}return Math.hypot(a,b)/Math.max(1,hi-lo);};
    const teacherEnergy=energy(440,.1,.3),studentEnergy=Math.max(...Array.from({length:12},(_,i)=>energy(1056,i*.1,i*.1+.1))); // Actual 1.2x playback.
    if(teacherEnergy<.01 || studentEnergy<.01)throw new Error(`Mixed audio missing: ${teacherEnergy}, ${studentEnergy}`);
    let toneAt=null;for(let at=0;at<1.2;at+=.025)if(energy(1056,at,at+.05)>.01){toneAt=at;break;}
    const expected=store.recordingTime(result.segments,marker);
    // decodeAudioData omits container timestamps. Verify AV timing on the actual video clock below.
    if(toneAt===null)throw new Error('Student tone absent');
    const video=document.createElement('video');video.controls=true;video.src=URL.createObjectURL(result.blob);document.body.append(video);
    await new Promise((yes,no)=>{video.onloadedmetadata=yes;video.onerror=no;});
    const mediaSource=synthetic.createMediaElementSource(video),analyser=synthetic.createAnalyser(),silent=synthetic.createGain();
    analyser.fftSize=2048;silent.gain.value=0;mediaSource.connect(analyser);analyser.connect(silent);silent.connect(synthetic.destination);
    const frame=document.createElement('canvas');frame.width=8;frame.height=8;const frameCtx=frame.getContext('2d');
    const spectrum=new Float32Array(analyser.frequencyBinCount);let audioAt=null,frameAt=null;
    await video.play();
    const until=performance.now()+4000;
    while(performance.now()<until && (audioAt===null || frameAt===null)){
      await new Promise(requestAnimationFrame);analyser.getFloatFrequencyData(spectrum);
      const bin=Math.round(1056/synthetic.sampleRate*analyser.fftSize);
      if(audioAt===null && Math.max(spectrum[bin-1],spectrum[bin],spectrum[bin+1])>-35)audioAt=video.currentTime;
      frameCtx.drawImage(video,0,0,8,8);
      if(frameAt===null && frameCtx.getImageData(4,4,1,1).data[0]>200)frameAt=video.currentTime;
    }
    video.pause();
    const avDriftMs=Math.abs(audioAt-frameAt)*1000,evidenceDriftMs=Math.abs(frameAt-expected)*1000;
    if(audioAt===null || frameAt===null || avDriftMs>500 || evidenceDriftMs>500)
      throw new Error(`Video-clock timing failed: audio=${audioAt}, frame=${frameAt}, expected=${expected}`);
    const seekAt=expected+.25;
    const seeked=new Promise((yes,no)=>{video.onseeked=yes;setTimeout(()=>no(new Error('Recorded video cannot seek')),3000);});
    video.currentTime=seekAt;await seeked;
    const canvas=document.createElement('canvas');canvas.width=8;canvas.height=8;
    const context=canvas.getContext('2d');context.drawImage(video,0,0,8,8);
    const brightness=context.getImageData(4,4,1,1).data[0];if(brightness<200)throw new Error('Video marker did not seek to expected frame');
    const resumedSeek=store.recordingTime(result.segments,result.segments[1].wallStart+250);
    const resumedFrame=new Promise((yes,no)=>{video.onseeked=yes;setTimeout(()=>no(new Error('Resume segment cannot seek')),3000);});
    video.currentTime=resumedSeek;await resumedFrame;context.drawImage(video,0,0,8,8);
    const red=context.getImageData(4,4,1,1).data;
    if(red[0]<200 || red[1]>50)throw new Error('Pause duration leaked into recording timeline');
    mediaSource.disconnect();analyser.disconnect();silent.disconnect();
    URL.revokeObjectURL(video.src);video.remove();audio.close();teacher.stop();synthetic.close();rec.dispose();
    window.__recordingFixture={...result,marker,seekAt};
    return {bytes:result.blob.size,mime:result.blob.type,segments:result.segments,teacherEnergy,studentEnergy,
      avDriftMs,evidenceDriftMs,brightness,resumedSeek,completed:messages.some(m=>m.type==='playback_done')};
  });
  await page.screenshot({path:'output/playwright/recording-ready.png',fullPage:true});
  return {result:errors.length?'FAILED':'PASSED',media,errors};
}
