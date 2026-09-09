import { FilesetResolver, GestureRecognizer } from "@mediapipe/tasks-vision";
import { handFeatures } from "./motionFeatures.js";
let model;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === "init") {
      const files = await FilesetResolver.forVisionTasks(
        import.meta.env.DEV
          ? "/node_modules/@mediapipe/tasks-vision/wasm"
          : "/models/wasm",
        true,
      );
      model?.close();
      model = await GestureRecognizer.createFromOptions(files, {
        baseOptions: {
          modelAssetPath: "/models/gesture_recognizer.task",
          delegate: "CPU",
        },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6,
      });
      self.postMessage({ type: "ready" });
    } else {
      const result = model.recognizeForVideo(data.image, data.time);
      self.postMessage({ type: "hands", hands: result.landmarks || [], summary: handFeatures(result) });
    }
  } catch {
    self.postMessage({
      type: "error",
      message: "手部检测暂不可用，请重新加载动作模型",
    });
  } finally {
    data.image?.close();
  }
};
