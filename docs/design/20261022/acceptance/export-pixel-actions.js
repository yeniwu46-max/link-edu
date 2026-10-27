async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5188/tests/pixel-actions-browser.html');
 await page.setViewportSize({width:1000,height:660});
 await page.waitForFunction(()=>!!window.__pixelPreview);
 const url=await page.evaluate(async()=>{
   const canvas=document.querySelector('#canvas canvas'),stream=canvas.captureStream(30),chunks=[];
   const recorder=new MediaRecorder(stream,{mimeType:'video/webm'});
   const stopped=new Promise(resolve=>recorder.onstop=()=>resolve(URL.createObjectURL(new Blob(chunks,{type:'video/webm'}))));
   recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.start();
   const wait=ms=>new Promise(r=>setTimeout(r,ms));
   for(const name of ['doze','confused','writing','speech']){window.__pixelPreview.action(name);await wait(name==='speech'?4400:2600)}
   recorder.stop();stream.getTracks().forEach(t=>t.stop());return stopped;
 });
 const download=page.waitForEvent('download');
 await page.evaluate(url=>{let a=document.createElement('a');a.href=url;a.download='pixel-actions-v2.webm';a.click()},url);
 await (await download).saveAs('docs/design/20261022/compact-implemented/pixel-actions-v2.webm');
 await page.waitForTimeout(2000);await page.getByRole('button',{name:'拿笔写字',exact:true}).click();await page.waitForTimeout(450);await page.screenshot({path:'docs/design/20261022/compact-implemented/pixel-actions-v2.png'});
 if(errors.length)throw Error(errors.join(';'));
 return {preview:'pixel-actions-v2.webm',errors};
}
