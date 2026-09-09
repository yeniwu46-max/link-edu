const button = document.getElementById("test-pose"),
  result = document.getElementById("result");
button.onclick = () => {
  button.disabled = true;
  result.textContent = "加载本地模型中…";
  const worker = new Worker(
    new URL("./services/pose.worker.js", import.meta.url),
    { type: "module" },
  );
  const timer = setTimeout(() => {
    worker.terminate();
    button.disabled = false;
    result.textContent = "失败：30秒内未完成加载/推理";
  }, 30000);
  worker.onerror = (event) => {
    clearTimeout(timer);
    button.disabled = false;
    result.textContent = "线程失败：" + event.message;
    worker.terminate();
  };
  worker.onmessage = async ({ data }) => {
    if (['hands_status', 'face_status'].includes(data.type)) return;
    if (data.type === "ready") {
      result.textContent = "本地模型加载成功，测试合成空白帧…";
      const canvas = new OffscreenCanvas(640, 480);
      canvas.getContext("2d").fillRect(0, 0, 640, 480);
      const image = await createImageBitmap(canvas);
      worker.postMessage({ image, time: performance.now() }, [image]);
    } else {
      clearTimeout(timer);
      result.textContent = JSON.stringify(data, null, 2);
      button.disabled = false;
      worker.terminate();
    }
  };
  worker.postMessage({ type: "init" });
};
