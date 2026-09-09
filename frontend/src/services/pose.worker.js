import { FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";
let model,
  handsWorker,
  handPending,
  handTimer,
  handsReady = false,
  files,
  previous = null;
async function initHands() {
  try {
    handPending?.reject(new Error("Hand worker replaced"));
    clearTimeout(handTimer);
    handsWorker?.terminate();
    handsReady = false;
    // MediaPipe 1.x consumes ModuleFactory once per module worker. Isolate models.
    const worker = (handsWorker = new Worker(
      new URL("./hands.worker.js", import.meta.url),
      { type: "module" },
    ));
    worker.onmessage = ({ data }) => {
      if (worker !== handsWorker || !handPending) return;
      clearTimeout(handTimer);
      const pending = handPending;
      handPending = null;
      if (data.type === "error") pending.reject(new Error(data.message));
      else pending.resolve(data.hands || []);
    };
    worker.onerror = () => {
      handPending?.reject(new Error("Hand worker failed"));
    };
    await handRequest({ type: "init" }, [], 10000);
    handsReady = true;
    self.postMessage({ type: "hands_status", status: "ready" });
  } catch (error) {
    handsReady = false;
    handsWorker?.terminate();
    self.postMessage({
      type: "hands_status",
      status: "failed",
      diagnostic: import.meta.env.DEV
        ? String(error.message).slice(0, 300)
        : undefined,
    });
  }
}
function handRequest(message, transfer, timeout = 3000) {
  return new Promise((resolve, reject) => {
    handPending = { resolve, reject };
    handTimer = setTimeout(
      () => reject(new Error("Hand model timed out")),
      timeout,
    );
    handsWorker.postMessage(message, transfer);
  }).finally(() => {
    clearTimeout(handTimer);
    handPending = null;
  });
}
self.onmessage = async ({ data }) => {
  try {
    if (data.type === "retry_hands") {
      await initHands();
      return;
    }
    if (data.type === "init") {
      // Vite cannot dynamically import public/*.js during development. Both paths are local.
      files = await FilesetResolver.forVisionTasks(
        import.meta.env.DEV
          ? "/node_modules/@mediapipe/tasks-vision/wasm"
          : "/models/wasm",
        true,
      );
      model?.close();
      model = await PoseLandmarker.createFromOptions(files, {
        baseOptions: {
          modelAssetPath: "/models/pose_landmarker_lite.task",
          delegate: "CPU",
        },
        runningMode: "VIDEO",
        numPoses: 1,
      });
      await initHands();
      self.postMessage({ type: "ready" });
      return;
    }
    if (!model) {
      data.image?.close();
      return;
    }
    const result = model.detectForVideo(data.image, data.time);
    let hands = [];
    if (handsReady) {
      try {
        const copy = await createImageBitmap(data.image);
        hands = await handRequest({ image: copy, time: data.time }, [copy]);
      } catch {
        handsWorker?.terminate();
        handsReady = false;
        self.postMessage({ type: "hands_status", status: "failed" });
      }
    }
    data.image.close();
    const p = result.landmarks?.[0];
    if (!p) {
      self.postMessage({
        type: "pose",
        landmarks: [],
        hands,
        data: { present: false, confidence: 0 },
      });
      previous = null;
      return;
    }
    const confidence = Math.min(
      ...[11, 12, 23, 24].map((i) => p[i].visibility ?? 0),
    );
    if (confidence < 0.6) {
      self.postMessage({
        type: "pose",
        landmarks: p,
        hands,
        data: { present: null, confidence },
      });
      previous = null; // Do not infer movement across an unobserved/occluded interval.
      return;
    }
    const sx = (p[11].x + p[12].x) / 2,
      sy = (p[11].y + p[12].y) / 2;
    const hx = (p[23].x + p[24].x) / 2,
      hy = (p[23].y + p[24].y) / 2;
    const center = (sx + hx) / 2;
    self.postMessage({
      type: "pose",
      landmarks: p,
      hands,
      data: {
        present: true,
        confidence,
        left_raised: p[15].visibility > 0.6 ? p[15].y < p[11].y : null,
        right_raised: p[16].visibility > 0.6 ? p[16].y < p[12].y : null,
        lean_degrees: Math.round(
          (Math.atan2(sx - hx, hy - sy) * 180) / Math.PI,
        ),
        center_x: center,
        movement: previous === null ? 0 : Math.abs(center - previous),
      },
    });
    previous = center;
  } catch (error) {
    data.image?.close();
    self.postMessage({
      type: "error",
      message: "动作模型不可用，请检查本地模型文件和浏览器支持",
      diagnostic: import.meta.env.DEV
        ? String(error.message).slice(0, 300)
        : undefined,
    });
  }
};
