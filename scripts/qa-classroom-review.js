// playwright-cli -s=report-refresh run-code --filename scripts/qa-classroom-review.js --raw
// All API responses are synthetic. Media, external network and real writes are blocked.
async (page) => {
  page.setDefaultTimeout(12000);
  page.setDefaultNavigationTimeout(15000);
  await page.unrouteAll({behavior:'ignoreErrors'});
  page.removeAllListeners('pageerror');
  page.removeAllListeners('dialog');
  const failures=[],errors=[],requests=[];
  const check=(value,message)=>{if(!value)failures.push(message);};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('dialog',dialog=>dialog.dismiss());
  await page.addInitScript(()=>{
    localStorage.setItem('link_token','synthetic-review-only');
    window.__devices=0;
    navigator.mediaDevices.getUserMedia=async()=>{window.__devices++;throw Error('Devices disabled in QA');};
  });
  const events=[
    {id:1,type:'transcript',at_ms:11000,data:{text:'只有每份一样大，才是平均分。请小林用自己的话解释。'}},
    {id:2,type:'student',at_ms:38000,data:{name:'小林',text:'每一份都一样大。',reply_id:'r1'}},
    {id:3,type:'playback',at_ms:42000,data:{reply_id:'r1',status:'playback_completed'}},
    {id:4,type:'vision',at_ms:50000,data:{observations:'教师展示了等分示意图。'}},
    {id:5,type:'transcript',at_ms:63000,data:{text:'刚才我说得不够准确：还需要在同一个整体中比较。'}},
    {id:6,type:'student',at_ms:100000,data:{name:'小雨',text:'分母越大，每份一定越大吗？',reply_id:'r2'}},
    {id:7,type:'playback',at_ms:102000,data:{reply_id:'r2',status:'playback_failed'}},
    {id:8,type:'transcript',at_ms:138000,data:{text:'先观察同一个整体，再比较每份的大小。'}},
    ...Array.from({length:55},(_,i)=>({id:20+i,type:'pose',at_ms:4000+i*4200,data:{present:i%3!==0,confidence:.7}})),
  ];
  const dims=[['clarity','表达清晰度',80],['pace','教学节奏',75],['interaction','互动设计',90],['posture','教态与站位',null],['questioning','提问质量',85],['structure','课堂结构',80]];
  const report={overall_score:82,coverage:'5/6',generated_at:'2026-09-10T00:12:00Z',notice:'AI 辅助评价，仅对有证据的维度评分。',
    dimensions:dims.map(([key,label,score])=>({key,label,score,reason:key==='posture'?'动作证据的可观察范围有限，不能据此判断整节课的非语言表达。暂不评分。':key==='clarity'?'教师使用“每份一样大”解释平均分，表达较为清楚。随后主动补充“同一个整体”的条件，复核时应考虑这次自我纠错，不将初始表述单独作为最终理解的依据。':'结合本节已有课堂记录进行分析；学生生成的文字与播放结果应分别核对，未播放内容不作为已完成互动。',event_ids:key==='posture'?[]:[1,3,4],source_ids:['s1']})),
    sources:[{id:'s1',title:'课堂提问与证据复核（测试资料）',type:'本地资料',location:'第 2 节',text:'结合学生解释与教师反馈复核课堂判断。',source:'QA synthetic fixture'}],
    motion_evidence:{status:'insufficient',sample_count:55,observed_samples:36,modalities:{body:{observed_samples:36,total_samples:55},hands:{observed_samples:12,total_samples:55},face:{observed_samples:28,total_samples:55}},observations:[{code:'hand_open_palm',description:'手掌展开',matched_samples:4,observed_samples:12,longest_observed_span_ms:4200,suggestion:'结合讲解语境复核，不按次数评分。',event_ids:[20]}],limitations:['采样比例不等于课堂时长比例。']}};
  const base={session_id:900,topic:'分数的初步认识',mode:'full',state:'ended',elapsed:250,created_at:'2026-09-10T00:07:41',report_state:'completed',report_version:2,students:{},events,report};
  const rooms={900:base,901:{...base,session_id:901,state:'active',report:null,report_state:'idle'},902:{...base,session_id:902,report_state:'insufficient',report_readiness:{reasons:['最终转写不足：需至少 2 段、80 字。','学生反馈不足：没有完整播放的回应。','动作捕捉不足：0 个有效样本。','未识别到足够的单人教师画面。']}},903:{...base,session_id:903,report_state:'failed',report_error:'报告生成超时，请重试。'},904:{...base,session_id:904,report_state:'running'}};
  let fail900=false,empty=false,runningReads=0;
  await page.route('**/*',async route=>{
    const request=route.request(),url={pathname:request.url().replace(/^http:\/\/[^/]+/,'').split('?')[0]};
    if(!request.url().startsWith('http://127.0.0.1:5188/'))return route.abort();
    if(!url.pathname.startsWith('/api/'))return route.continue();
    requests.push({path:url.pathname,method:request.method()});
    if(request.method()!=='GET')return route.fulfill({status:400,json:{message:'QA blocks writes'}});
    if(url.pathname==='/api/auth/me')return route.fulfill({json:{id:1,name:'林晓',role_label:'师范生'}});
    if(url.pathname==='/api/classroom/capabilities')return route.fulfill({json:{services:{},budget:{}}});
    if(url.pathname==='/api/classroom/sessions')return route.fulfill({json:{items:empty?[]:Object.values(rooms).map(r=>({...r,events:undefined}))}});
    if(url.pathname.includes('/evidence/'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#82d2c5"/><circle cx="320" cy="180" r="100" fill="#171c22"/></svg>'});
    const id=url.pathname.match(/^\/api\/classroom\/sessions\/(\d+)$/)?.[1];
    if(id==='900' && fail900)return route.fulfill({status:500,json:{message:'QA injected failure'}});
    if(id==='904' && ++runningReads>1)return route.fulfill({json:{...rooms[id],report_state:'completed'}});
    if(rooms[id])return route.fulfill({json:rooms[id]});
    return route.fulfill({status:404,json:{message:'QA fixture not found'}});
  });
  await page.setViewportSize({width:1440,height:1080});
  await page.goto('http://127.0.0.1:5188/ai-review');
  await page.getByRole('heading',{name:'一节课的教学剖面'}).waitFor();
  check(page.url().endsWith('/ai-review?classroom=900'),'Default AI review must open latest ended classroom');
  check(await page.locator('.dimension-row').count()===6,'Six dimensions missing');
  check(await page.getByRole('button',{name:'教态与站位：暂不评分'}).isVisible(),'Null posture must not become zero');
  check(await page.locator('.report-metrics>div').nth(2).innerText()==='确认完整播放\n1次','Playback counting mismatch');
  const layouts=[];
  for(const width of [1440,1024,768,320]){
    await page.setViewportSize({width,height:1080});
    await page.waitForTimeout(200);
    const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
    layouts.push(layout);check(layout.scrollWidth<=width,`Horizontal overflow at ${width}`);
    await page.screenshot({path:`output/playwright/ai-review-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1080});
  await page.getByRole('button',{name:'教态与站位：暂不评分'}).click();
  check(await page.locator('.dimension-insight').getByText('暂不评分',{exact:true}).isVisible(),'Dimension selection not changing evidence');
  await page.getByRole('button',{name:'表达清晰度：80 分'}).click();
  await page.getByRole('button',{name:'查看 3 条证据'}).click();
  const drawer=page.getByRole('dialog',{name:'表达清晰度 · 证据',exact:true});
  await drawer.waitFor();
  check(await drawer.locator('#review-evidence-3').isVisible(),'Technical playback evidence must be retained');
  await drawer.getByRole('searchbox',{name:'查找证据'}).fill('#3');
  check(await drawer.locator('li[id^="review-evidence-"]').count()===1,'Evidence filtering broken');
  await drawer.getByRole('searchbox',{name:'查找证据'}).fill('');
  await drawer.getByRole('button',{name:'查看截图'}).click();
  await page.getByRole('dialog',{name:'课堂截图证据'}).getByRole('img').waitFor();
  await page.keyboard.press('Tab');
  check(await page.evaluate(()=>document.activeElement.closest('dialog')?.getAttribute('aria-label')==='课堂截图证据'),'Nested evidence focus escaped');
  await page.keyboard.press('Escape');
  check(await drawer.isVisible(),'Closing screenshot should preserve evidence list');
  await page.keyboard.press('Escape');
  check(await page.getByRole('button',{name:'查看 3 条证据'}).evaluate(el=>el===document.activeElement),'Evidence focus not restored');
  await page.getByText('查看动作线索与检测边界',{exact:true}).click();
  check(await page.getByText('采样比例不等于课堂时长比例。',{exact:true}).isVisible(),'Motion limitations missing');
  await page.getByRole('button',{name:'查看相关记录',exact:true}).click();
  check(await page.getByRole('dialog',{name:'手掌展开 · 证据'}).locator('#review-evidence-20').isVisible(),'Motion evidence did not resolve');
  await page.keyboard.press('Escape');
  await page.getByText('查看动作线索与检测边界',{exact:true}).click();
  await page.locator('.report-correction summary').click();
  await page.getByRole('button',{name:'重新评课',exact:true}).click(); // native confirmation dismissed above
  check(!requests.some(r=>r.method!=='GET'),'Cancelled confirmation must not generate');
  await page.locator('.report-correction summary').click();
  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.locator('.dimension-insight').evaluate(el=>getComputedStyle(el).animationName)==='none','Reduced motion missing');
  await page.emulateMedia({media:'print'});
  check(await page.locator('.report-print-dimensions section').count()===6 && await page.locator('.report-print-dimensions').isVisible(),'Print must include all six conclusions');
  await page.emulateMedia({media:'screen'});
  await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
  check(await page.locator('.report-fold:not([open])').count()===0,'Print must expand methods and sources');
  await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
  check(await page.locator('.report-fold[open]').count()===0,'Print must restore collapsed reading state');
  await page.goto('http://127.0.0.1:5188/classroom');
  await page.getByRole('button',{name:'历史课堂',exact:true}).click();
  const history=page.getByRole('dialog',{name:'历史课堂',exact:true});
  await history.getByRole('link').first().click();
  await page.getByRole('heading',{name:'一节课的教学剖面'}).waitFor();
  check(page.url().includes('/ai-review?classroom=900'),'History must navigate to AI review not classroom');
  await page.getByLabel('历史课堂',{exact:true}).selectOption('902');
  await page.getByRole('heading',{name:'这节课的证据，还不足以形成评课'}).waitFor();
  check(await page.locator('.report-blocked li').count()===4,'All insufficiency reasons must be visible');
  check(!await page.locator('.report-score-ring').count() && !await page.locator('.report-correction').count(),'Insufficient data must hide stale scores and retry');
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=903');
  await page.getByText('报告生成超时，请重试。',{exact:true}).waitFor();
  check(await page.getByText('以下保留的是上一版报告，本次尚未生成成功。',{exact:true}).isVisible(),'Stale report must be clearly marked');
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=904');
  await page.getByText('评课进行中',{exact:true}).waitFor();
  await page.getByText('已完成',{exact:true}).waitFor({timeout:10000});
  check(runningReads>1,'Pending reports must poll without regeneration');
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=901');
  await page.getByRole('heading',{name:'这节课堂还未结束'}).waitFor();
  check(await page.getByRole('link',{name:'返回课堂',exact:true}).getAttribute('href')==='/classroom?session=901','Active report should return to correct classroom');
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=999');
  await page.getByText('这节课堂不存在，或你没有查看权限。请选择其他课堂。',{exact:false}).waitFor();
  check(!await page.locator('.report-score-ring').count(),'404 must not fall back to another report');
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=invalid');
  await page.getByText('课堂编号无效，请从历史课堂重新进入。',{exact:false}).waitFor();
  check(!await page.locator('.report-score-ring').count(),'Invalid ID must not select another classroom');
  fail900=true;
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=900');
  await page.getByText('报告读取失败，暂未取得最新结果。请重试。',{exact:false}).waitFor();
  fail900=false;
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByRole('heading',{name:'一节课的教学剖面'}).waitFor();
  empty=true;
  await page.goto('http://127.0.0.1:5188/ai-review');
  await page.getByRole('heading',{name:'你的第一份评课，等待一节真实课堂'}).waitFor();
  empty=false;
  await page.goto('http://127.0.0.1:5188/ai-review?classroom=900');
  await page.getByRole('heading',{name:'一节课的教学剖面'}).waitFor();
  await page.waitForTimeout(450);
  await page.screenshot({path:'output/playwright/ai-review-final.png',fullPage:true});
  check(await page.evaluate(()=>window.__devices)===0,'Report must not request devices');
  check(!requests.some(r=>r.method!=='GET'),'Report reading must not write or call paid AI');
  check(!requests.some(r=>r.path.includes('feedback')),'Classroom report must not request legacy feedback');
  check(errors.length===0,`Browser errors: ${errors.join('; ')}`);
  const result={result:failures.length?'FAILED':'PASSED',failures,errors,layouts,apiReads:requests.length};
  await page.evaluate(result=>window.__reviewQAResult=result,result);
  return result;
}
