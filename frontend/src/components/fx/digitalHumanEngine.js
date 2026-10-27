import { assistantPixelFrame, ASSISTANT_ACTIONS, pixelSource } from '../../services/pixelCharacters.js'
import { loadPixelAtlas, drawPixelSprite } from './pixelSpriteCanvas.js'

export async function createDigitalHuman(host, { policy, onReady, signal }) {
  const image=await loadPixelAtlas(pixelSource('assistant'),signal)
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d')
  if(!ctx){image.close();throw new Error('Canvas unavailable')}
  canvas.dataset.renderer='pixel-2d';host.append(canvas)
  let frames=0,renderMs=0,disposed=false,visible=true,raf=0,last=0,state='idle',level=0,pointer=0
  const began=performance.now()
  function stop(){cancelAnimationFrame(raf);raf=0;last=0}
  function render(){
    if(disposed)return
    const start=performance.now(),frame=assistantPixelFrame(state,level,{now:start-began,reduced:policy.reducedMotion,pointer})
    ctx.clearRect(0,0,canvas.width,canvas.height)
    drawPixelSprite(ctx,image,frame,{x:0,y:0,width:canvas.width,height:canvas.height},false,pointer)
    host.dataset.action=ASSISTANT_ACTIONS[frame];renderMs+=performance.now()-start;frames++
  }
  function tick(now){
    raf=0;if(disposed||!visible||!policy.visible)return
    if(now-last>=1000/30-.5){render();last=now}
    if(!policy.reducedMotion)raf=requestAnimationFrame(tick)
  }
  function wake(){
    if(disposed||!visible||!policy.visible)return
    render();if(!raf&&!policy.reducedMotion)raf=requestAnimationFrame(tick)
  }
  function resize(){
    if(disposed)return
    const {width,height}=host.getBoundingClientRect()
    canvas.width=Math.max(1,Math.round(width));canvas.height=Math.max(1,Math.round(height));wake()
  }
  const observer=new ResizeObserver(resize);observer.observe(host)
  const handle={
    snapshot(){render();return canvas.toDataURL('image/png')},
    stats(){return {frames,renderMs,renderer:'pixel-2d',textures:disposed?0:1,disposed}},
    setPolicy(next){policy=next;stop();resize()},
    setVisible(value){visible=value;if(!value)stop();else wake()},
    setState(next,audioLevel=0){state=next;level=audioLevel;if(policy.reducedMotion)wake()},
    setPointer(value){pointer=Math.max(-1,Math.min(1,value));if(policy.reducedMotion)wake()},
    dispose(){if(disposed)return;disposed=true;stop();observer.disconnect();signal?.removeEventListener('abort',handle.dispose);image.close();canvas.remove();canvas.width=canvas.height=0},
  }
  signal?.addEventListener('abort',handle.dispose,{once:true})
  resize();onReady?.(canvas);return handle
}
