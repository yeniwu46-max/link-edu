import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';
import { bodyFeatures } from './motionFeatures.js';
import { MotionTaskClient } from './motionTaskClient.js';
let model, previous = null;
const hands = new MotionTaskClient(
  () => new Worker(new URL('./hands.worker.js', import.meta.url), {type:'module'}),
  status => self.postMessage({type:'hands_status',status}));
const face = new MotionTaskClient(
  () => new Worker(new URL('./faces.worker.js', import.meta.url), {type:'module'}),
  status => self.postMessage({type:'face_status',status}));

self.onmessage = async ({data}) => {
  try {
    if (data.type === 'retry_hands') { await Promise.all([hands.start(), face.start()]); return; }
    if (data.type === 'init') {
      const files = await FilesetResolver.forVisionTasks(
        import.meta.env.DEV ? '/node_modules/@mediapipe/tasks-vision/wasm' : '/models/wasm', true);
      model?.close(); previous = null;
      model = await PoseLandmarker.createFromOptions(files, {
        baseOptions:{modelAssetPath:'/models/pose_landmarker_lite.task',delegate:'CPU'},
        runningMode:'VIDEO',numPoses:2,minPoseDetectionConfidence:.6,minPosePresenceConfidence:.6,minTrackingConfidence:.6,
      });
      await Promise.all([hands.start(), face.start()]);
      self.postMessage({type:'ready'}); return;
    }
    if (!model) return;
    const result = model.detectForVideo(data.image, data.time);
    const [handResult, faceResult] = await Promise.all([hands.frame(data.image, data.time), face.frame(data.image, data.time)]);
    const body = bodyFeatures(result.landmarks, data.image.width / data.image.height || 4/3);
    let handSummary = handResult?.summary || {status: hands.ready ? 'no_detection' : 'failed'};
    let faceSummary = faceResult?.summary || {status: face.ready ? 'no_detection' : 'failed'};
    const multiple = body.status === 'multiple' || faceSummary.status === 'multiple';
    if (multiple) { handSummary = {status:'multiple'}; faceSummary = {status:'multiple'}; }
    const p = result.landmarks?.[0];
    // Keep legacy summary fields for existing clients, but use v2 per-modality evidence.
    const confidence = p ? Math.min(...[11,12,23,24].map(i=>p[i]?.visibility ?? 0)) : 0;
    const present = !p ? false : multiple || confidence < .6 ? null : true;
    const center = body.center_x ?? null;
    const summary = {present, confidence, motion_version:2, body: multiple ? {status:'multiple'} : body,
      hands:handSummary, face:faceSummary};
    if (present) Object.assign(summary, {left_raised:body.left_raised,right_raised:body.right_raised,
      lean_degrees:body.lean_degrees,center_x:center,
      movement:previous === null || center === null ? 0 : Math.abs(center-previous)});
    previous = present ? center : null;
    self.postMessage({type:'pose', captured_at:data.time, landmarks:multiple ? [] : p || [],
      hands:multiple ? [] : handResult?.hands || [], face:multiple ? [] : faceResult?.face || [], data:summary});
  } catch (error) {
    previous = null;
    self.postMessage({type:'error',message:'动作模型不可用，请检查本地模型文件和浏览器支持',
      diagnostic:import.meta.env.DEV ? String(error.message).slice(0,300) : undefined});
  } finally { data.image?.close(); }
};
