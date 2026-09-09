import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";
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
      model = await HandLandmarker.createFromOptions(files, {
        baseOptions: {
          modelAssetPath: "/models/hand_landmarker.task",
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
      const result = model.detectForVideo(data.image, data.time);
      self.postMessage({ type: "hands", hands: result.landmarks || [] });
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
