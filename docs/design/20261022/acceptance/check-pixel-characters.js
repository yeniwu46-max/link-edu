async (page) => {
  const check=(ok,message)=>{if(!ok)throw new Error(message)};
  await page.setViewportSize({width:1440,height:1000});await page.reload();
  await page.waitForSelector('.student-stage[data-renderer="ready"]');
  await page.getByRole('button',{name:'对话布局',exact:true}).click();
  const host=page.locator('.student-stage__canvas');
  check(await host.locator('canvas').evaluate(c=>!!c.getContext('2d')),'not Canvas 2D');
  for(const [button,attribute,expected] of [['raised','data-ming-action','raised'],['thinking','data-yu-action','thinking'],['speaking','data-yu-action','speaking'],['done','data-yu-action','happy']]){
    await page.getByRole('button',{name:button,exact:true}).click();
    await page.waitForFunction(([attr,value])=>document.querySelector('.student-stage__canvas').getAttribute(attr)===value,[attribute,expected]);
  }
  await page.getByRole('button',{name:'idle',exact:true}).click();
  await page.getByRole('button',{name:'小明，点击邀请提问或反驳',exact:true}).focus();await page.keyboard.press('ArrowLeft');
  await page.waitForFunction(()=>document.querySelector('.student-stage__canvas').dataset.mingAction==='turn');
  await page.keyboard.press('Home');
  await page.getByRole('button',{name:'减少动态：关',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.student-stage__canvas').dataset.motion==='static');
  const hash=await host.locator('canvas').evaluate(c=>c.toDataURL());await page.waitForTimeout(500);
  check(hash===await host.locator('canvas').evaluate(c=>c.toDataURL()),'reduced motion still animates');
  await page.getByRole('button',{name:'raised',exact:true}).click();
  check(await host.getAttribute('data-ming-action')==='raised','reduced motion lost raised state');
  await page.getByRole('button',{name:'检查缓存像素',exact:true}).click();
  const pixels=JSON.parse(await page.getByTestId('frame-pixels').textContent());
  for(const id of ['ming','yu','lin'])check(pixels[id].filled>1000,'record cache missing offscreen '+id);
  await page.getByRole('button',{name:'页面可见：是',exact:true}).click();
  check(await host.getAttribute('data-effect-visible')==='false','hidden loop not stopped');
  await page.getByRole('button',{name:'页面可见：否',exact:true}).click();
  await page.getByRole('button',{name:'WebGL：可用',exact:true}).click();
  await page.waitForSelector('.student-stage[data-renderer="ready"]');
  await page.waitForSelector('.digital-human canvas');
  check(await page.locator('.digital-human canvas').count()===1,'assistant missing without WebGL');
  await page.getByRole('button',{name:'像素图集：正常',exact:true}).click();
  await page.waitForSelector('.student-stage[data-renderer="fallback"]');
  check(await page.locator('.student-card .pixel-sprite').count()===3,'per-student static fallback missing');
  await page.getByRole('button',{name:'像素图集：缺失',exact:true}).click();
  await page.waitForSelector('.student-stage[data-renderer="ready"]');
  await page.getByRole('button',{name:'重复卸载 3 次',exact:true}).click();
  await page.waitForTimeout(5600);await page.waitForSelector('.student-stage[data-renderer="ready"]');
  check(await page.locator('.student-stage canvas').count()===1,'student canvas leaked');
  check(await page.locator('.digital-human canvas').count()===1,'assistant canvas leaked');
  await page.getByRole('button',{name:'减少动态：开',exact:true}).click();
  await page.getByRole('button',{name:'WebGL：不可用',exact:true}).click();
  await page.waitForSelector('.student-stage[data-renderer="ready"]');
  await page.getByRole('button',{name:'默认布局',exact:true}).click();
  await page.screenshot({path:'output/playwright/pixel-default-layout.png'});
  return {checks:'pixel actions, audio mouth, keyboard turn, reduced motion, hidden, no WebGL, fallback, remount cleanup, all three recording slots',pixels};
}
