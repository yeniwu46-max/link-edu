import { FilesetResolver, FaceLandmarker } from '@mediapipe/tasks-vision';
import { faceFeatures } from './motionFeatures.js';
let model;
self.onmessage = async ({data}) => {
  try {
    if (data.type === 'init') {
      const files = await FilesetResolver.forVisionTasks(
        import.meta.env.DEV ? '/node_modules/@mediapipe/tasks-vision/wasm' : '/models/wasm', true);
      model?.close();
      model = await FaceLandmarker.createFromOptions(files, {
        baseOptions: {modelAssetPath: '/models/face_landmarker.task', delegate: 'CPU'},
        runningMode: 'VIDEO', numFaces: 2, minFaceDetectionConfidence: .6,
        minFacePresenceConfidence: .6, minTrackingConfidence: .6,
        outputFaceBlendshapes: true, outputFacialTransformationMatrixes: false,
      });
      self.postMessage({type: 'ready'});
    } else {
      const result = model.detectForVideo(data.image, data.time);
      const summary = faceFeatures(result, data.image.width / data.image.height || 4 / 3);
      // Mesh remains inside local workers/UI; never sent to the backend.
      self.postMessage({type: 'face', face: summary.status === 'observed' ? result.faceLandmarks[0] : [], summary});
    }
  } catch {
    self.postMessage({type: 'error', message: '面部动作检测暂不可用，身体和语音仍可继续'});
  } finally { data.image?.close(); }
};
