import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const compiled=await build({entryPoints:[fileURLToPath(new URL('../src/services/pose.worker.js',import.meta.url))],
  bundle:true,write:false,format:'cjs',platform:'node',external:['@mediapipe/tasks-vision'],
  define:{'import.meta.env.DEV':'false','import.meta.url':JSON.stringify(import.meta.url)}});

test('low-confidence gap resets movement baseline and reports unknown pose',async()=>{
  let landmarks=null, closed=0;
  const messages=[];
  const self={postMessage:m=>messages.push(m)};
  const model={detectForVideo:()=>({landmarks:landmarks?[landmarks]:[]})};
  vm.runInNewContext(compiled.outputFiles[0].text,{self,clearTimeout,setTimeout,require:()=>({
    FilesetResolver:{forVisionTasks:async()=>({})},PoseLandmarker:{createFromOptions:async()=>model}})});
  await self.onmessage({data:{type:'init'}});
  const frame=async(x,confidence)=>{
    landmarks=Array.from({length:33},()=>({x,y:.5,visibility:confidence}));
    await self.onmessage({data:{time:performance.now(),image:{close(){closed++;}}}});
    return messages.at(-1).data;
  };
  assert.equal((await frame(.2,1)).movement,0);
  assert.equal((await frame(.5,.2)).present,null);
  assert.equal((await frame(.8,1)).movement,0);
  landmarks=null;
  await self.onmessage({data:{time:performance.now(),image:{close(){closed++;}}}});
  assert.equal(messages.at(-1).data.present,false); assert.equal(closed,4);
});

test('body and both hands stay local; seated upper-body landmarks survive unknown summary',async()=>{
  const messages=[];
  let body=Array.from({length:33},()=>({x:.5,y:.5,visibility:1}));
  body[23].visibility=body[24].visibility=.1;
  let hands=Array.from({length:2},()=>Array.from({length:21},()=>({x:.4,y:.3,z:0})));
  let closed=0;
  const self={postMessage:m=>messages.push(m)};
  vm.runInNewContext(compiled.outputFiles[0].text,{self,URL,clearTimeout,setTimeout,createImageBitmap:async()=>({close(){}}),
    Worker:class {terminate(){} postMessage(data){this.onmessage({data:data.type==='init'?{type:'ready'}:{type:'hands',hands}});}},
    require:()=>({
    FilesetResolver:{forVisionTasks:async()=>({})},
    PoseLandmarker:{createFromOptions:async()=>({detectForVideo:()=>({landmarks:body?[body]:[]})})},
    HandLandmarker:{createFromOptions:async()=>({detectForVideo:()=>({landmarks:hands}),close(){}})},
  })});
  await self.onmessage({data:{type:'init'}});
  assert.ok(messages.some(m=>m.type==='hands_status'&&m.status==='ready'));
  const frame=async()=>{await self.onmessage({data:{time:1,image:{close(){closed++;}}}});return messages.at(-1);};
  const result=await frame();
  assert.equal(result.data.present,null); assert.equal(result.landmarks.length,33); assert.equal(result.hands.length,2);
  assert.equal(result.data.landmarks,undefined); assert.equal(result.data.hands,undefined);
  body=null; hands=[];
  const empty=await frame(); assert.equal(empty.landmarks.length,0);assert.equal(empty.hands.length,0);assert.equal(closed,2);
});

test('missing hand model keeps body detector ready and supports hand retry',async()=>{
  const messages=[];let fail=true;
  const self={postMessage:m=>messages.push(m)};
  vm.runInNewContext(compiled.outputFiles[0].text,{self,URL,clearTimeout,setTimeout,
    Worker:class {terminate(){} postMessage(){this.onmessage({data:fail?{type:'error',message:'missing'}:{type:'ready'}});}},
    require:()=>({
    FilesetResolver:{forVisionTasks:async()=>({})},PoseLandmarker:{createFromOptions:async()=>({detectForVideo:()=>({landmarks:[]})})},
    HandLandmarker:{createFromOptions:async()=>{if(fail)throw new Error('missing');return {detectForVideo:()=>({landmarks:[]})};}},
  })});
  await self.onmessage({data:{type:'init'}});
  assert.equal(messages.at(-1).type,'ready');assert.ok(messages.some(m=>m.status==='failed'));
  fail=false; await self.onmessage({data:{type:'retry_hands'}});
  assert.equal(messages.at(-1).status,'ready');
});
