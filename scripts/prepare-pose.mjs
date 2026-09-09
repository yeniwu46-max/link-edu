import { mkdir, cp, writeFile, stat, rename } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const target = path.join(root, "frontend/public/models");
await mkdir(target, { recursive: true });
await cp(
  path.join(root, "frontend/node_modules/@mediapipe/tasks-vision/wasm"),
  path.join(target, "wasm"),
  { recursive: true },
);
const model = path.join(target, "pose_landmarker_lite.task");
if (
  await stat(model)
    .then((s) => s.size > 1000000)
    .catch(() => false)
) {
  console.log("Existing local pose model retained.");
} else {
  const url =
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
  const response = await fetch(url, { signal: AbortSignal.timeout(60000) });
  if (!response.ok)
    throw new Error(`Pose model download failed: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length < 1000000) throw new Error("Unexpected pose model size");
  await writeFile(model, bytes);
  console.log(`Installed local pose model (${bytes.length} bytes).`);
}
// Fixed model bundle versions from the official MediaPipe model distribution.
for (const [filename, url] of [
  ['gesture_recognizer.task', 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task'],
  ['face_landmarker.task', 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'],
]) {
  const destination = path.join(target, filename);
  if (await stat(destination).then(s => s.size > 1000000).catch(() => false)) {
    console.log(`Existing local ${filename} retained.`); continue;
  }
  const response = await fetch(url, {signal: AbortSignal.timeout(60000)});
  if (!response.ok) throw new Error(`${filename}: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length < 1000000) throw new Error(`Unexpected ${filename} size`);
  await writeFile(destination + '.download', bytes);
  await rename(destination + '.download', destination);
  console.log(`Installed local ${filename} (${bytes.length} bytes).`);
}
console.log(
  "WASM copied locally. Browser runtime does not fetch models from a CDN.",
);
const handModel = path.join(target, "hand_landmarker.task");
if (
  await stat(handModel)
    .then((s) => s.size > 1000000)
    .catch(() => false)
) {
  console.log("Existing local hand model retained.");
} else {
  const response = await fetch(
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    { signal: AbortSignal.timeout(60000) },
  );
  if (!response.ok)
    throw new Error(`Hand model download failed: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length < 1000000) throw new Error("Unexpected hand model size");
  await writeFile(handModel, bytes);
  console.log(`Installed local hand model (${bytes.length} bytes).`);
}
