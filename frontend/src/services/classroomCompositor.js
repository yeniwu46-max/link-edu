import { studentPresentation } from './classroomStudent.js';

function lines(ctx,text,width,maxLines=3) {
  const rows=[''];
  for (const char of String(text||'')) {
    if (ctx.measureText(rows.at(-1)+char).width>width) rows.push('');
    rows[rows.length-1]+=char;
  }
  return rows.slice(-maxLines);
}
export function createClassroomPainter(snapshot) {
  const images=new Map();
  let terminalKey='',hideAt=Infinity;
  for (const id of ['ming','yu','lin']) for (const pose of ['listening','raised']) {
    const src=`/assets/students/${id}-${pose}.png`, image=new Image(); image.src=src; images.set(src,image);
  }
  return (ctx,canvas)=>{
    const s=snapshot(), {width:w,height:h}=canvas;
    const terminal=['done','failed'].includes(s.reply?.phase);
    const key=`${s.reply?.replyId}:${s.reply?.id}:${s.reply?.phase}`;
    if(terminal && key!==terminalKey){terminalKey=key;hideAt=performance.now()+15000;}
    if(!terminal){terminalKey='';hideAt=Infinity;}
    ctx.fillStyle='#0d1018';ctx.fillRect(0,0,w,h);
    const video=s.video;
    if (video?.readyState>=2 && video.videoWidth) {
      const scale=Math.min(w/video.videoWidth,480/video.videoHeight);
      const vw=video.videoWidth*scale,vh=video.videoHeight*scale;
      ctx.save(); if(s.mirror){ctx.translate(w,0);ctx.scale(-1,1);}
      ctx.drawImage(video,(w-vw)/2,(480-vh)/2,vw,vh);ctx.restore();
    }
    ctx.font='20px sans-serif';ctx.fillStyle='#fff';ctx.fillText('LINK · 模拟课堂',24,32);
    if(s.captionText && s.captions) {
      ctx.font='24px sans-serif';const rows=lines(ctx,`${s.captionLabel}：${s.captionText}`,900);
      ctx.fillStyle='#000b';ctx.fillRect(164,462-rows.length*30,952,rows.length*30+12);
      ctx.fillStyle='#fff';rows.forEach((line,i)=>ctx.fillText(line,190,486-rows.length*30+i*30));
    }
    ['ming','yu','lin'].forEach((id,i)=>{
      const x=24+i*420, r=s.reply?.studentId===id?s.reply:null;
      const presentation=studentPresentation(id,{raised:s.raised===id,speaking:s.playbackStudent===id,reply:r,interactionState:s.studentStates?.[id]?.interaction_state});
      const image=images.get(presentation.src);
      ctx.fillStyle='#191e2a';ctx.fillRect(x,488,392,220);
      const bob=s.reducedMotion?0:Math.sin(performance.now()/750+i)*2;
      const frame=s.studentFrame, slot=frame?.slots?.[id];
      if(frame?.canvas?.width && slot?.width && slot?.height) {
        ctx.drawImage(frame.canvas,slot.x,slot.y,slot.width,slot.height,x+10,518,175,175);
      } else if(image?.complete && image.naturalWidth)ctx.drawImage(image,x+10,518+bob,175,175);
      ctx.fillStyle='#fff';ctx.font='20px sans-serif';ctx.fillText({ming:'小明',yu:'小雨',lin:'小林'}[id],x+206,680);
      ctx.font='16px sans-serif';ctx.fillStyle='#b9c4d7';ctx.fillText(presentation.label,x+206,704);
      if(r?.text && !['idle','failed'].includes(r.phase) && performance.now()<hideAt) {
        ctx.fillStyle='#f0f3f8';ctx.fillRect(x+174,510,206,138);ctx.fillStyle='#141a28';ctx.font='17px sans-serif';
        lines(ctx,r.text,186,6).forEach((line,j)=>ctx.fillText(line,x+184,536+j*20));
      }
    });
  };
}
