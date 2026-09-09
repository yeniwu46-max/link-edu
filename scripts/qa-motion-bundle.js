// Browser smoke check for a production Vite preview on port 5191.
// No device access, credentials, backend writes, or cloud requests.
async page => {
  await page.route('**/*', route => /^http:\/\/127\.0\.0\.1:5191\/(assets|models)\//.test(route.request().url()) ? route.continue() : route.abort());
  const scripts = await page.locator('script[src]').evaluateAll(nodes => nodes.map(n=>n.src));
  let workerPath;
  for (const url of scripts.filter(url=>url.startsWith('http://127.0.0.1:5191/assets/'))) {
    const source = await (await page.request.get(url)).text();
    workerPath ||= source.match(/\/assets\/pose\.worker-[\w-]+\.js/)?.[0];
  }
  if (!workerPath) throw new Error('Production pose worker not found in page bundle');
  return page.evaluate(async workerPath => {
    return new Promise((resolve, reject) => {
      const worker = new Worker(workerPath, {type:'module'});
      const statuses = {}, started = performance.now();
      const timer = setTimeout(() => { worker.terminate(); reject(new Error('Model smoke test timed out')); }, 30000);
      worker.onerror = error => { clearTimeout(timer); worker.terminate(); reject(new Error(error.message)); };
      worker.onmessage = async ({data}) => {
        if (data.type.endsWith('_status')) { statuses[data.type] = data.status; return; }
        if (data.type === 'ready') {
          const canvas = new OffscreenCanvas(640,480);
          canvas.getContext('2d').fillRect(0,0,640,480);
          const image = await createImageBitmap(canvas);
          worker.postMessage({image,time:performance.now()},[image]); return;
        }
        clearTimeout(timer); worker.terminate();
        if (data.type !== 'pose' || statuses.hands_status !== 'ready' || statuses.face_status !== 'ready') return reject(new Error(JSON.stringify({statuses,data})));
        if (['body','hands','face'].some(key=>data.data[key].status!=='no_detection')) return reject(new Error('Blank frame must not become motion evidence'));
        resolve({result:'PASSED',statuses,data:data.data,elapsed_ms:Math.round(performance.now()-started)});
      };
      worker.postMessage({type:'init'});
    });
  }, workerPath);
}
