import { mkdir, cp, writeFile, stat } from "node:fs/promises";
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
console.log(
  "WASM copied locally. Browser runtime does not fetch models from a CDN.",
);
