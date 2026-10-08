// Transport owns no classroom records; every payload is scoped to one assistant session.
import { ClassroomAudio } from './classroomAudio.js'
export class AssistantClient {
  constructor({api,onEvent,Audio=ClassroomAudio,Socket=WebSocket}) { this.api=api;this.onEvent=onEvent;this.Audio=Audio;this.Socket=Socket;this.epoch=0;this.cancelled=new Set() }
  send(type,payload={}) { if(this.socket?.readyState===1&&this.session)this.socket.send(JSON.stringify({type,session_id:this.session,...payload})) }
  async start(mode='text') {
    this.stop();const epoch=this.epoch;this.mode=mode
    this.onEvent({type:'state',state:'connecting'})
    try {
      const cap=(await this.api.get('/assistant/capabilities',{skipBusy:true,timeout:8000})).data
      if(epoch!==this.epoch)return false
      if(!cap[mode+'_available'])throw new Error(cap.message||'助手服务未配置，可使用下方的使用帮助')
      const {data}=await this.api.post('/assistant/ticket',{mode},{skipBusy:true,timeout:8000})
      if(epoch!==this.epoch)return false
      await new Promise((resolve,reject)=>{
        const url=new URL('/api/assistant/live',location.href);url.protocol=url.protocol==='https:'?'wss:':'ws:'
        const socket=this.socket=new this.Socket(url)
        const timer=setTimeout(()=>reject(new Error('助手连接超时')),10000)
        this.rejectConnect=()=>{clearTimeout(timer);reject(new Error('连接已取消'))}
        socket.onopen=()=>{if(epoch===this.epoch)socket.send(JSON.stringify({ticket:data.ticket}))}
        socket.onmessage=({data:raw})=>{
          if(epoch!==this.epoch)return
          let event;try{event=JSON.parse(raw)}catch{return}
          if(event.type==='ready'){this.session=event.session_id;clearTimeout(timer);this.rejectConnect=null;resolve();return}
          if(event.type==='error'&&!this.session){clearTimeout(timer);reject(new Error(event.message));return}
          this.receive(event)
        }
        socket.onerror=()=>{clearTimeout(timer);reject(new Error('助手连接失败'))}
        socket.onclose=()=>{clearTimeout(timer);if(epoch!==this.epoch)return;reject(new Error('连接已关闭'));this.stop();this.onEvent({type:'closed',message:'助手连接已关闭，可重新开始'})}
      })
      if(epoch!==this.epoch)return false
      if(mode==='voice') {
        this.audio=new this.Audio((type,payload)=>this.send(type,payload),level=>this.onEvent({type:'level',level}),
          (turn,state)=>{if(turn!==this.turn||this.cancelled.has(turn))return;this.onEvent({type:'state',state:state==='playing'?'speaking':'listening'})},{playbackRate:1})
        await this.audio.start()
        if(epoch!==this.epoch)return false
      }
      this.onEvent({type:'state',state:mode==='voice'?'listening':'idle'});return true
    } catch(error) {if(epoch!==this.epoch)return false;this.stop();this.onEvent({type:'error',message:error.name==='NotAllowedError'?'麦克风未授权，仍可使用文字问答':error.message||'语音启动失败'});return false}
  }
  receive(event) {
    if(!this.session||event.session_id!==this.session)return
    if(event.type==='cancel'){const id=event.cancelled_turn_id;this.cancelled.add(id);this.audio?.cancel(id);if(id===this.turn)this.turn=null;this.onEvent(event);return}
    if(event.type==='recognition'&&event.final){if(this.turn)this.audio?.cancel(this.turn);this.turn=event.turn_id}
    if(event.turn_id&&(event.turn_id!==this.turn||this.cancelled.has(event.turn_id)))return
    if(event.type==='audio')this.audio?.chunk(event.turn_id,event.audio,event.rate)
    else if(event.type==='audio_end')this.audio?.end(event.turn_id)
    else if(event.type==='closed'){this.stop();this.onEvent(event)}
    else if(event.type==='error'){this.audio?.cancel(this.turn);this.onEvent(event)}
    else this.onEvent(event)
  }
  interrupt(){if(this.turn){this.cancelled.add(this.turn);this.audio?.cancel(this.turn)}this.send('cancel');this.onEvent({type:'state',state:this.mode==='voice'?'listening':'idle'})}
  stop(){this.epoch++;this.rejectConnect?.();this.rejectConnect=null;this.send('stop');this.session=null;this.turn=null;this.cancelled.clear();const socket=this.socket;this.socket=null;if(socket){socket.onclose=null;socket.close()}const audio=this.audio;this.audio=null;audio?.close();this.onEvent({type:'level',level:0})}
}
