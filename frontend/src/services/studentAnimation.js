// Timeline state is visual only. It never changes classroom learning evidence.
export const PIXEL_V2 = '/assets/characters/pixel/v2/'
export function createStudentAnimation(manifest, index = 0) {
  let clip = null, started = 0, standing = false, lastSpeaking = false, ambientSlot = -1
  let recover = null
  const frames = name => manifest.clips[name]
  const result = (frame, action) => ({ atlas: 2, frame, action })
  function begin(name, now) { clip = name; started = now }
  function sample(now, motion, { reduced = false, legacy = 0, force = null } = {}) {
    if (reduced) { clip=null; standing=lastSpeaking=!!motion.speaking; return motion.speaking ? result(frames('mouth')[motion.level > .08 ? 1 : 0],'speaking') : {atlas:1,frame:legacy,action:'static'} }
    if (motion.speaking && !lastSpeaking) { begin('rise',now); recover=null }
    if (!motion.speaking && lastSpeaking) {
      // If playback ends mid-rise, reverse only the distance already travelled.
      const count=clip==='rise' ? Math.min(8,Math.floor(Math.max(0,now-started)/100)+1) : 8
      recover=frames('rise').slice(0,count).reverse(); begin('sit',now)
    }
    lastSpeaking=!!motion.speaking
    if (motion.speaking) {
      if (clip==='rise' && now-started<800) return result(frames('rise')[Math.floor(Math.max(0,now-started)/100)],'rise')
      standing=true;clip=null
      return result(frames('mouth')[motion.level>.08?1:0],'speaking')
    }
    if (clip==='sit') {
      const sequence=recover||frames('sit'), n=Math.floor(Math.max(0,now-started)/100)
      if(n<sequence.length)return result(sequence[n],'sit')
      clip=null;standing=false;recover=null
    }
    if (motion.raised || motion.thinking || motion.failed || motion.acknowledged || motion.completed || motion.turn) {
      clip=null
      return {atlas:1,frame:legacy,action:'response'}
    }
    if (force && clip!==force) begin(force,now)
    const slot=Math.floor(now/18000), phase=now%18000
    // One student owns each dozing slot; others alternate writing and reading.
    if(!clip && slot!==ambientSlot && phase>1500){
      ambientSlot=slot
      begin(force || (slot%3===index ? 'doze' : ['writing','reading','confused'][(slot+index)%3]),now)
    }
    if(clip) {
      const n=Math.floor(Math.max(0,now-started)/100)
      const seq=clip==='writing' ? [...frames('pickup'),...frames('write'),...frames('write'),...frames('write'),...frames('putdown')] : frames(clip)
      if(seq && n<seq.length)return result(seq[n],clip)
      clip=null
    }
    return result(0,'listening')
  }
  return { sample }
}
