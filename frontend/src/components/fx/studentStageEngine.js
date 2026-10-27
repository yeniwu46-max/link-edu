import { studentMotionState, studentRenderQuality } from '../../services/studentStageState.js'
import { PIXEL_BASE, studentPixelFrame, STUDENT_ACTIONS } from '../../services/pixelCharacters.js'
import { createStudentAnimation, PIXEL_V2 } from '../../services/studentAnimation.js'
import { registerSequence, drawSequence } from './pixelSequenceCanvas.js'
import { drawPixelSprite, loadPixelAtlas } from './pixelSpriteCanvas.js'

export async function createStudentStage(host, { signal, policy: initialPolicy, getSlots, onModelState, modelBase = PIXEL_BASE }) {
  const began = performance.now(), avatars = new Map(), rects = new Map()
  const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas unavailable')
  canvas.setAttribute('aria-hidden', 'true'); canvas.dataset.renderer = 'pixel-2d'; host.append(canvas)
  const frameCanvas = document.createElement('canvas'), frameContext = frameCanvas.getContext('2d')
  let snapshot = null, state = {}, policy = initialPolicy, visible = true, disposed = false, capture = false
  let visualTime=0, lastVisual=0, lastPaint=-Infinity, manifest=null
  let raf = 0, previous = 0, sampledAt = 0, frames = 0, renderCost = 0, lastCapture = 0, closeView = false
  function updateSlots() {
    const root = host.getBoundingClientRect()
    rects.clear()
    for (const slot of getSlots()) {
      const r = slot.element.getBoundingClientRect(), clip = slot.clip?.getBoundingClientRect() || root
      if (r.width && r.height) rects.set(slot.id, { x:r.left-root.left, y:r.top-root.top, width:r.width, height:r.height,
        clip:{x:Math.max(r.left,clip.left)-root.left,y:Math.max(r.top,clip.top)-root.top,
          width:Math.max(0,Math.min(r.right,clip.right)-Math.max(r.left,clip.left)),
          height:Math.max(0,Math.min(r.bottom,clip.bottom)-Math.max(r.top,clip.top))} })
    }
  }
  function resize() {
    if (disposed) return
    const width = Math.max(1,host.clientWidth), height = Math.max(1,host.clientHeight)
    if (canvas.width !== width || canvas.height !== height) { canvas.width=width; canvas.height=height }
    host.dataset.quality = '30'; updateSlots()
  }
  function currentFrame(id, avatar, now) {
    const motion = studentMotionState(id,state), reply = state.reply?.studentId===id ? state.reply : null
    const legacy = studentPixelFrame({...motion, failed:reply?.phase==='failed', confused:state.studentStates?.[id]?.interaction_state==='confused'},
      {now,offset:avatar.offset,acknowledged:now<avatar.nodUntil,completed:now<avatar.happyUntil,
        turn:avatar.turn||avatar.pointer*.3,reduced:policy.reducedMotion})
    return avatar.animation ? avatar.animation.sample(now,{...motion,failed:reply?.phase==='failed',acknowledged:now<avatar.nodUntil,completed:now<avatar.happyUntil,turn:avatar.turn||avatar.pointer*.3},{reduced:policy.reducedMotion,legacy,force:state.previewAction}) : {atlas:1,frame:legacy,action:STUDENT_ACTIONS[legacy]}
  }
  function render(now) {
    if (disposed) return
    if(!policy.reducedMotion && now-lastPaint<1000/30)return
    lastPaint=now
    const started = performance.now()
    if(lastVisual)visualTime+=Math.max(0,Math.min(100,now-lastVisual))
    lastVisual=now
    ctx.clearRect(0,0,canvas.width,canvas.height)
    const cache = frameContext && (!snapshot || capture || !lastCapture) && (!lastCapture || now-lastCapture>=1000/24)
    if (cache) { frameCanvas.width=768; frameCanvas.height=256 }
    const slots={}; let index=0
    for (const [id,avatar] of avatars) {
      const frame=currentFrame(id,avatar,visualTime),rect=rects.get(id),facing=avatar.turn||avatar.pointer
      host.dataset[id+'Action']=frame.atlas===1 ? STUDENT_ACTIONS[frame.frame] : frame.action
      host.dataset[id+'Frame']=String(frame.frame)
      const draw=(context,slot,close=false)=>frame.atlas===2 ? drawSequence(context,avatar.sequence,manifest,avatar.anchors,frame.frame,slot,close) : drawPixelSprite(context,avatar.image,frame.frame,slot,close,facing)
      if (cache) {
        const slot={x:index*256,y:0,width:256,height:256}
        draw(frameContext,slot);slots[id]=slot
      }
      if(rect?.clip.width && rect.clip.height) {
        ctx.save();ctx.beginPath();ctx.rect(rect.clip.x,rect.clip.y,rect.clip.width,rect.clip.height);ctx.clip()
        draw(ctx,rect,closeView);ctx.restore()
      }
      index++
    }
    if(cache){snapshot={canvas:frameCanvas,slots};lastCapture=now}
    frames++;renderCost+=performance.now()-started
  }
  function tick(now) {
    raf=0
    if(disposed||!visible||!policy.visible||policy.reducedMotion)return
    const interval=1000/studentRenderQuality(policy.finePointer).fps
    if(now-previous>=interval-.5){render(now);previous=now-(now-previous)%interval}
    if(!sampledAt)sampledAt=now
    if(now-sampledAt>=2000){
      host.dataset.renderFps=(frames*1000/(now-sampledAt)).toFixed(1)
      host.dataset.renderMs=(renderCost/Math.max(1,frames)).toFixed(2)
      frames=renderCost=0;sampledAt=now
    }
    raf=requestAnimationFrame(tick)
  }
  function sync() {
    cancelAnimationFrame(raf);raf=0;lastVisual=0;previous=sampledAt=frames=renderCost=0
    host.dataset.motion=policy.reducedMotion?'static':'animated'
    host.dataset.effectVisible=String(visible&&policy.visible)
    if(disposed||!visible||!policy.visible)return
    lastCapture=0;render(performance.now())
    if(!policy.reducedMotion)raf=requestAnimationFrame(tick)
  }
  function dispose() {
    if(disposed)return
    disposed=true;cancelAnimationFrame(raf);observer.disconnect();signal?.removeEventListener('abort',dispose)
    for(const avatar of avatars.values()){avatar.image.close();avatar.sequence?.close()}
    avatars.clear();rects.clear();snapshot=null;frameCanvas.width=frameCanvas.height=0
    canvas.remove();canvas.width=canvas.height=0;host.dataset.disposed='true'
  }
  const observer=new ResizeObserver(()=>{resize();sync()});observer.observe(host)
  signal?.addEventListener('abort',dispose,{once:true})
  try {
    if(modelBase===PIXEL_BASE){try{const response=await fetch(PIXEL_V2+'manifest.json',{signal});if(response.ok)manifest=await response.json()}catch{}}
    await Promise.all(['ming','yu','lin'].map(async(id,index)=>{
      try {
        const image=await loadPixelAtlas(modelBase+id+'.png',signal)
        if(disposed){image.close();return}
        const avatar={image,offset:index*5370,turn:0,pointer:0,nodUntil:0,happyUntil:0}
        avatars.set(id,avatar)
        if(manifest){try{const sequence=await loadPixelAtlas(PIXEL_V2+id+'.png',signal);if(disposed){sequence.close();return}avatar.sequence=sequence;avatar.anchors=registerSequence(sequence,manifest,id);avatar.animation=createStudentAnimation(manifest,index)}catch{host.dataset[id+'Sequence']='fallback'}}
        resize();sync();onModelState(id,'ready')
      }catch(error){if(!disposed&&!signal?.aborted)onModelState(id,'fallback')}
    }))
    if(signal?.aborted||disposed)throw new DOMException('Aborted','AbortError')
    if(!avatars.size)throw new Error('No pixel characters available')
    host.dataset.loadMs=(performance.now()-began).toFixed(1);resize();sync()
    return {
      setState(next){
        const oldReply=state.reply
        if(next.reply?.phase==='done'&&(oldReply?.phase!=='done'||oldReply?.replyId!==next.reply?.replyId)){
          const avatar=avatars.get(next.reply.studentId);if(avatar)avatar.happyUntil=visualTime+1800
        }
        state=next;if(policy.reducedMotion&&visible&&policy.visible){lastCapture=0;render(performance.now())}
      },
      setPolicy(next){policy=next;resize();sync()},
      setVisible(next){visible=next;sync()},
      setCapture(next){capture=next;lastCapture=0;if(next)render(performance.now())},
      setPointer(id,value){const avatar=avatars.get(id);if(avatar)avatar.pointer=policy.finePointer&&!policy.reducedMotion?value:0},
      setRotation(id,value){const avatar=avatars.get(id);if(avatar){avatar.turn=value;lastCapture=0;render(performance.now())}},
      setView(close){closeView=close;render(performance.now())},
      acknowledge(id){const avatar=avatars.get(id);if(avatar&&!policy.reducedMotion)avatar.nodUntil=visualTime+900},
      snapshot:()=>snapshot,
      refreshSlots(){resize();if(visible&&policy.visible)render(performance.now())},
      dispose,
    }
  }catch(error){dispose();throw error}
}
