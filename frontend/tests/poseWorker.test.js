import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const compiled=await build({entryPoints:[fileURLToPath(new URL('../src/services/pose.worker.js',import.meta.url))],
  bundle:true,write:false,format:'cjs',platform:'node',external:['@mediapipe/tasks-vision'],
  define:{'import.meta.env.DEV':'false'}});

test('low-confidence gap resets movement baseline and reports unknown pose',async()=>{
  let landmarks=null, closed=0;
  const messages=[];
  const self={postMessage:m=>messages.push(m)};
  const model={detectForVideo:()=>({landmarks:landmarks?[landmarks]:[]})};
  vm.runInNewContext(compiled.outputFiles[0].text,{self,require:()=>({
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
