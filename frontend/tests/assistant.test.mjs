import test from 'node:test'
import assert from 'node:assert/strict'
import { AssistantClient } from '../src/services/assistantClient.js'
import { tourKey,tourSeen,saveTour } from '../src/utils/onboarding.js'
globalThis.location={href:'http://localhost:5188/'}
class Socket {
 static all=[]
 constructor(url){this.url=String(url);this.sent=[];this.readyState=1;Socket.all.push(this);queueMicrotask(()=>this.onopen?.())}
 send(raw){const data=JSON.parse(raw);this.sent.push(data);if(data.ticket)queueMicrotask(()=>this.onmessage?.({data:JSON.stringify({type:'ready',session_id:'session-'+Socket.all.length})}))}
 close(){this.closed=true;this.readyState=3}
 event(event){this.onmessage({data:JSON.stringify(event)})}
}
class Audio {
 static all=[]
 constructor(send,level,playback,options){this.chunks=[];this.cancelled=[];this.options=options;Audio.all.push(this)}
 async start(){this.started=true}
 chunk(...args){this.chunks.push(args)}
 cancel(id){this.cancelled.push(id)}
 end(id){this.endId=id}
 close(){this.closed=true}
}
const api={get:async()=>({data:{text_available:true,voice_available:true}}),post:async()=>({data:{ticket:'short-lived'}})}
function setup(overrides={}){const events=[];const client=new AssistantClient({api,onEvent:e=>events.push(e),Socket,Audio,...overrides});return{client,events}}
test('voice uses first-frame ticket, session IDs and natural 1x playback',async()=>{const{client}=setup();await client.start('voice');assert.equal(client.audio.options.playbackRate,1);assert.ok(!client.socket.url.includes('ticket'));assert.equal(client.socket.sent[0].ticket,'short-lived');client.send('text',{text:'问题'});assert.equal(client.socket.sent.at(-1).session_id,client.session);client.stop()})
test('cancelled and old-session audio cannot animate or play',async()=>{const{client}=setup();await client.start('voice');const socket=client.socket,session_id=client.session;socket.event({type:'recognition',session_id,turn_id:'t1',final:true,text:'测试'});socket.event({type:'audio',session_id,turn_id:'t1',audio:'AAAA',rate:24000});assert.equal(client.audio.chunks.length,1);client.interrupt();socket.event({type:'audio',session_id,turn_id:'t1',audio:'AAAA'});socket.event({type:'audio',session_id:'old',turn_id:'t1',audio:'AAAA'});assert.equal(client.audio.chunks.length,1);client.stop()})
test('close releases microphone/playback and socket; text never starts capture',async()=>{const{client}=setup();await client.start('voice');const audio=client.audio,socket=client.socket;client.stop();assert.ok(audio.closed&&socket.closed);await client.start('text');assert.equal(client.audio,null);client.stop()})
test('closing during capabilities prevents a late connection',async()=>{let resolve;const{client}=setup({api:{get:()=>new Promise(r=>resolve=r)}});const pending=client.start('voice');client.stop();resolve({data:{voice_available:true}});assert.equal(await pending,false);assert.equal(client.socket,null)})
test('permission rejection releases resources and reports text alternative',async()=>{class Denied extends Audio{async start(){throw Object.assign(new Error('denied'),{name:'NotAllowedError'})}}const{client,events}=setup({Audio:Denied});assert.equal(await client.start('voice'),false);assert.ok(events.some(e=>e.message?.includes('文字')));assert.ok(Audio.all.at(-1).closed)})
test('missing credits/config never opens socket',async()=>{const n=Socket.all.length;const{client,events}=setup({api:{get:async()=>({data:{voice_available:false,message:'额度不可用'}})}});assert.equal(await client.start('voice'),false);assert.equal(Socket.all.length,n);assert.equal(events.at(-1).message,'额度不可用')})
test('tour completion isolates user and version; storage denial is harmless',()=>{const map=new Map(),storage={getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v)};saveTour(1,'skipped',storage);assert.equal(tourSeen(1,storage),true);assert.equal(tourSeen(2,storage),false);assert.match(tourKey(1),/2026-10-1/);assert.doesNotThrow(()=>saveTour(2,'completed',{setItem(){throw Error()}}))})
