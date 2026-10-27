// Register alpha silhouettes at the feet; source rectangles include measured atlas gutters.
export function registerSequence(image, manifest, id) {
  const surface=document.createElement('canvas')
  surface.width=image.width;surface.height=image.height
  const ctx=surface.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0)
  const {data}=ctx.getImageData(0,0,image.width,image.height)
  const frames=manifest.frames?.[id] || Array.from({length:manifest.columns*manifest.rows},(_,f)=>({
    x:Math.round(f%manifest.columns*image.width/manifest.columns),y:Math.round(Math.floor(f/manifest.columns)*image.height/manifest.rows),
    width:Math.floor(image.width/manifest.columns),height:Math.floor(image.height/manifest.rows)}))
  const anchors=frames.map(({x:left,y:top,width,height})=>{
    let x0=width,x1=0,y1=0
    for(let y=Math.floor(height*.55);y<height;y++)for(let x=0;x<width;x++){
      if(data[((top+y)*image.width+left+x)*4+3]>150){x0=Math.min(x0,x);x1=Math.max(x1,x);y1=y}
    }
    return {x:(x0+x1)/2,y:y1}
  })
  surface.width=surface.height=0
  return {frames,anchors,extent:Math.max(...frames.map(f=>Math.max(f.width,f.height)))}
}
export function drawSequence(ctx,image,manifest,registration,frame,rect,close=false) {
  const source=registration.frames[frame],anchor=registration.anchors[frame]
  if(!source || !anchor)return
  const scale=Math.min(rect.width,rect.height)*(close?1.3:.94)/registration.extent
  const x=rect.x+rect.width/2-anchor.x*scale
  const y=rect.y+rect.height*.97-anchor.y*scale
  ctx.save();ctx.beginPath();ctx.rect(rect.x,rect.y,rect.width,rect.height);ctx.clip();ctx.imageSmoothingEnabled=false
  ctx.drawImage(image,source.x,source.y,source.width,source.height,Math.round(x),Math.round(y),source.width*scale,source.height*scale)
  ctx.restore()
}
