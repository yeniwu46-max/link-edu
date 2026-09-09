export const CAMERA_HEIGHTS = [1020, 720, 360];
export function cameraConstraints(value) {
  const height = CAMERA_HEIGHTS.includes(Number(value)) ? Number(value) : 720;
  return {width:{ideal:Math.round(height*16/9/2)*2},height:{ideal:height},frameRate:{ideal:24,max:30}};
}
export function inferenceSize(width, height) {
  const scale = Math.min(1, 640 / width, 480 / height);
  return {resizeWidth:Math.max(1,Math.round(width*scale)),resizeHeight:Math.max(1,Math.round(height*scale))};
}
