import test from 'node:test';
import assert from 'node:assert/strict';
import * as status from '../src/services/classroomStatus.js';

function configured() {
  return {services:Object.fromEntries(['dialogue','asr','tts'].map(key=>[key,{configured:true,pricing_confirmed:true,status:'unverified'}])),
    budget:{pricing_confirmed:true,stopped:false}};
}
const reasons=(overrides={})=>status.classroomStartBlockers({capabilities:configured(),consent:true,cameraConsent:true,...overrides});

test('start blockers list every missing consent, rather than a generic disabled message',()=>{
  const blocked=reasons({consent:false,cameraConsent:false});
  assert.deepEqual(blocked.map(r=>r.code),['audio_consent','camera_consent']);
  assert.match(blocked[0].message,/同意语音识别与 AI 评课/);
  assert.match(blocked[1].message,/同意摄像头开启/);
});

test('failed capability reads are not presented as loading, even with stale configured data',()=>{
  const failure='课堂后端暂不可用（HTTP 500），请确认后端服务已启动。';
  const blocked=reasons({capabilitiesError:failure});
  assert.equal(blocked.length,1); assert.equal(blocked[0].message,failure);
  assert.equal(blocked[0].action,'refresh');
  assert.equal(reasons({capabilities:null,capabilitiesLoading:true})[0].code,'capabilities_loading');
  assert.equal(reasons({capabilities:null})[0].action,'refresh');
});

test('start names each unavailable service and unconfirmed price or budget',()=>{
  const capabilities=configured();
  capabilities.services.dialogue.configured=false;
  capabilities.services.asr.pricing_confirmed=false;
  delete capabilities.services.tts;
  capabilities.budget.pricing_confirmed=false;
  const blocked=reasons({capabilities});
  assert.deepEqual(blocked.map(r=>r.code),['dialogue_config','asr_pricing','tts_missing','budget_pricing']);
  assert.match(blocked[0].message,/对话与评课.*未配置/);
  assert.match(blocked[1].message,/语音识别.*单价/);
  assert.match(blocked[2].message,/学生语音/);
});

test('budget stop and missing budget are explained; optional services and unverified probes do not block',()=>{
  const capabilities=configured();
  capabilities.budget.stopped=true;
  assert.equal(reasons({capabilities})[0].code,'budget_stopped');
  delete capabilities.budget;
  assert.equal(reasons({capabilities})[0].code,'budget_missing');
  const ready=configured();
  ready.services.vision={configured:false,pricing_confirmed:false};
  ready.budget.credits={accounts:{vision:{stopped:true},test:{stopped:true}}};
  assert.deepEqual(reasons({capabilities:ready}),[]);
});

test('busy state explains device initialization and ready state has no blockers',()=>{
  assert.match(reasons({busy:true,state:'idle'})[0].message,/摄像头.*授权/);
  assert.match(reasons({busy:true,state:'connecting'})[0].message,/麦克风.*摄像头/);
  assert.deepEqual(reasons(),[]);
});

test('capability errors distinguish login, timeout, unreachable backend and HTTP errors without raw data',()=>{
  assert.match(status.classroomCapabilitiesError({response:{status:401}}),/重新登录/);
  assert.match(status.classroomCapabilitiesError({code:'ECONNABORTED'}),/超时/);
  assert.match(status.classroomCapabilitiesError({code:'ERR_NETWORK'}),/后端.*启动/);
  const message=status.classroomCapabilitiesError({response:{status:500,data:{message:'private-key-should-not-display'}}});
  assert.match(message,/HTTP 500/); assert.ok(!message.includes('private-key'));
});
