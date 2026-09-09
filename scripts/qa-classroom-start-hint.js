// Run after qa-classroom-ui.js in the same isolated CLI browser session.
// Mock capability responses only; existing fixture blocks devices and all API writes.
async page => {
  const failures=[],errors=[],writes=[];
  const check=(ok,message)=>{if(!ok)failures.push(message);};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(request.url().includes('/api/') && request.method()!=='GET')writes.push(request.url());});
  const seed=await page.evaluate(()=>JSON.parse(JSON.stringify(window.__classroomQA.capabilities.value)));
  for(const key of ['dialogue','asr','tts']) seed.services[key]={...seed.services[key],configured:true,pricing_confirmed:true,status:'unverified'};
  seed.budget={...seed.budget,pricing_confirmed:true,stopped:false};
  const copySeed=()=>JSON.parse(JSON.stringify(seed));
  let data=copySeed(), mode='failed';
  await page.route('**/api/classroom/capabilities',route=>mode==='failed'
    ? route.fulfill({status:500,json:{message:'Synthetic backend unavailable'}})
    : route.fulfill({json:data}));
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.waitForFunction(()=>Boolean(window.__classroomQA?.capabilitiesError.value));
  const feedback=page.locator('#class-start-hint');
  const start=page.getByRole('button',{name:'开始授课',exact:true});
  const refresh=page.getByRole('button',{name:'重新读取状态',exact:true});
  check(await start.isDisabled(),'Backend failure must disable start');
  check((await feedback.innerText()).includes('HTTP 500'),'HTTP failure reason missing beside start');
  check(!(await feedback.innerText()).includes('正在读取'),'Failed read must not remain loading');
  check(!(await page.locator('.classroom-services').innerText()).includes('读取中'),'Service summary must not show perpetual loading after failure');
  check((await feedback.innerText()).includes('同意语音识别') && (await feedback.innerText()).includes('同意摄像头'),'Both missing consents should be listed');
  await page.getByRole('checkbox',{name:'同意语音识别与 AI 评课',exact:true}).check();
  await page.getByRole('checkbox',{name:'同意摄像头开启',exact:true}).check();
  check(await start.isDisabled(),'Consents cannot bypass backend failure');
  check((await start.getAttribute('title')).includes('HTTP 500'),'Disabled button tooltip must explain reason');
  check(await start.getAttribute('aria-describedby')==='class-start-hint','Screen reader description missing');
  await page.screenshot({path:'output/playwright/classroom-start-backend-error.png',fullPage:true});
  mode='ok'; await refresh.click();
  await page.waitForFunction(()=>window.__classroomQA.capabilities.value && !window.__classroomQA.capabilitiesLoading.value);
  // A newly identified provider requires renewed audio consent, as in the existing privacy flow.
  await page.getByRole('checkbox',{name:'同意语音识别与 AI 评课',exact:true}).check();
  await page.waitForFunction(()=>!document.querySelector('.class-controls button').disabled);
  check((await feedback.innerText()).includes('已就绪'),'Success should remove stale failure reasons');
  mode='failed'; await page.evaluate(()=>window.__classroomQA.refreshCapabilities());
  check(await start.isDisabled(),'Failed refresh must not trust cached configured data');
  await page.evaluate(()=>{window.__classroomQA.error.value='';});
  check((await feedback.innerText()).includes('HTTP 500'),'Unrelated alert dismissal erased start reason');
  mode='ok'; data=copySeed();
  data.services.dialogue.configured=false; data.services.asr.pricing_confirmed=false; data.budget.stopped=true;
  await refresh.click();
  await page.waitForFunction(()=>!window.__classroomQA.capabilitiesLoading.value);
  const blockedText=await feedback.innerText();
  check(/对话与评课.*未配置/.test(blockedText),'Missing service config reason missing');
  check(/语音识别.*单价/.test(blockedText),'Unconfirmed price reason missing');
  check(blockedText.includes('授课额度已达到停止线'),'Budget stop reason missing');
  await page.getByRole('button',{name:'查看配置与额度',exact:true}).click();
  check(await page.getByRole('dialog',{name:'课堂设置',exact:true}).isVisible(),'Settings action must open dialog');
  await page.getByRole('button',{name:'关闭课堂设置',exact:true}).click();
  for(const width of [1440,1024,768,320]) {
    await page.setViewportSize({width,height:900});
    check(await feedback.isVisible(),`Reason panel hidden at ${width}`);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Horizontal overflow at ${width}`);
    await page.screenshot({path:`output/playwright/classroom-start-blocked-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1080});
  data=copySeed(); await refresh.click();
  await page.waitForFunction(()=>!window.__classroomQA.capabilitiesLoading.value);
  check(await start.isEnabled(),'Resolved config should unlock start without reopening camera');
  await page.evaluate(()=>{window.__classroomQA.busy.value=true;});
  check((await feedback.innerText()).includes('摄像头授权弹窗'),'Pending preview explanation missing');
  await page.evaluate(()=>{const live=window.__classroomQA;live.busy.value=false;
    live.room.value={session_id:901,state:'active',mode:'full'};live.state.value='disconnected';live.capabilities.value.budget.stopped=true;});
  check(await page.getByRole('button',{name:'重新连接',exact:true}).isDisabled(),'Reconnect must share the same gate');
  check((await feedback.innerText()).includes('暂不可重新连接'),'Reconnect explanation missing');
  check(await page.evaluate(()=>window.__deviceRequests)===0,'Start hints must not request devices');
  check(writes.length===0,'Refresh must never invoke paid probes or create classroom');
  check(errors.length===0,`Browser errors: ${errors.join('; ')}`);
  await page.unroute('**/api/classroom/capabilities');
  return {result:failures.length?'FAILED':'PASSED',failures,errors,writes};
}
