async (page) => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  await page.reload();
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'对话布局',exact:true}).click();
  const video = await page.locator('.motion-frame video').elementHandle();
  const stage = await page.locator('.student-stage').elementHandle();
  await page.getByRole('button',{name:'模拟流式对话',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-message.student').length>0);
  await page.waitForFunction(()=>document.querySelector('.conversation-messages')?.textContent.includes('就是这个整体的二分之一。'));
  check(await page.locator('.conversation-message').count() >= 2,'stream history missing');
  for(let i=0;i<3;i++){
    await page.getByRole('button',{name:'默认布局',exact:true}).click();
    if(i===0){const camera=await page.locator('.motion-frame').boundingBox(),bar=await page.locator('.player-console').boundingBox(),students=await page.locator('.fullscreen-students').boundingBox();check(camera.height>=270&&bar.y>=camera.y+camera.height-1&&students.y>=bar.y+bar.height-1,'default layout changed order');}
    await page.getByRole('button',{name:'对话布局',exact:true}).click();
  }
  check(await video.evaluate(node=>node===document.querySelector('.motion-frame video')),'video remounted');
  check(await stage.evaluate(node=>node===document.querySelector('.student-stage')),'student stage remounted');
  await page.locator('.classroom-camera').scrollIntoViewIfNeeded();
  const panels=await page.evaluate(()=>{
    const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return{x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom};};
    return{chat:r('.classroom-conversation'),students:r('.fullscreen-students'),area:r('.classroom-workspace'),frame:r('.motion-frame'),bar:r('.player-console')};
  });
  check(panels.students.width>=240&&panels.students.width<=300&&panels.chat.width>panels.students.width,'student rail width');
  check(panels.students.x>panels.chat.x && panels.bar.y>=panels.area.bottom-1,'wrong desktop layout');
  const handle=page.getByRole('button',{name:'拖动教师小窗，方向键移动，Home 复位'});
  const box=await handle.boundingBox();
  await page.mouse.move(box.x+30,box.y+15);await page.mouse.down();
  await page.mouse.move(panels.area.right+300,panels.area.bottom+200,{steps:12});await page.mouse.up();
  const dragged=await page.locator('.motion-frame').boundingBox();
  check(dragged.x>panels.students.x,'cannot drag across columns');
  check(dragged.x+dragged.width<=panels.area.right+1 && dragged.y+dragged.height<=panels.area.bottom+1,'drag escaped workspace');
  await handle.focus();await page.keyboard.press('Home');
  const reset=await page.locator('.motion-frame').boundingBox();
  await page.keyboard.press('ArrowLeft');
  check((await page.locator('.motion-frame').boundingBox()).x<reset.x,'keyboard move failed');
  await page.getByRole('button',{name:'填充对话历史',exact:true}).click();
  await page.locator('.conversation-scroll').evaluate(el=>{el.dispatchEvent(new WheelEvent('wheel',{deltaY:-100}));el.scrollTop=0;el.dispatchEvent(new Event('scroll'));});
  await page.getByRole('button',{name:'模拟流式对话',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.conversation-scroll').scrollTop===0 && !!document.querySelector('.conversation-latest'));
  await page.waitForTimeout(3300);
  check(await page.locator('.conversation-scroll').evaluate(el=>el.scrollTop===0),'history reading was pulled to latest');
  await page.getByRole('button',{name:'↓ 回到最新',exact:true}).click();
  check(await page.locator('.conversation-scroll').evaluate(el=>el.scrollHeight-el.scrollTop-el.clientHeight<48),'latest failed');
  await page.locator('.classroom-camera').scrollIntoViewIfNeeded();
  await page.screenshot({path:'output/playwright/classroom-dialogue-classic.png'});
  await page.getByRole('button',{name:'切换验收主题',exact:true}).click();
  await page.locator('.classroom-camera').scrollIntoViewIfNeeded();
  await page.screenshot({path:'output/playwright/classroom-dialogue-academy.png'});
  await page.getByRole('button',{name:'全屏放大',exact:true}).click();
  check(await page.locator('.classroom-camera').evaluate(el=>el.classList.contains('dialogue-layout')&&el.classList.contains('expanded')),'fullscreen lost layout');
  await page.getByRole('button',{name:'退出全屏',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.locator('.classroom-camera').scrollIntoViewIfNeeded();
  const mobile=await page.evaluate(()=>{
    const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return{x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom};};
    return{chat:r('.classroom-conversation'),students:r('.fullscreen-students'),area:r('.classroom-workspace'),frame:r('.motion-frame')};
  });
  check(mobile.chat.y>mobile.students.y,'mobile panels did not stack');
  check(mobile.frame.width===160,'mobile camera size');
  check(mobile.frame.right<=mobile.area.right+1 && mobile.frame.x>=mobile.area.x-1,'mobile drag bound');
  await page.waitForFunction(()=>{const el=document.querySelector('.conversation-scroll');return el.scrollHeight-el.scrollTop-el.clientHeight<48;});
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile horizontal overflow');
  await page.screenshot({path:'output/playwright/classroom-dialogue-mobile.png'});
  await page.reload();
  await page.waitForSelector('.classroom-camera.dialogue-layout');
  console.log('PASS: stream, same media/stage nodes, layout geometry, drag/keyboard bounds, scroll retention, themes, fullscreen, mobile, remembered layout');
}
