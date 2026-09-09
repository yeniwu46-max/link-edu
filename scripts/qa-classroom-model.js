// Local model smoke check, no camera/microphone and no cloud API.
async (page) => {
  return await page.evaluate(async () => {
    const worker = new Worker(window.__qaModelWorkerUrl || '/src/services/pose.worker.js', {type:'module'});
    const statuses = [];
    try {
      return await new Promise((resolve,reject) => {
        const timeout = setTimeout(()=>reject(new Error('Local model initialization timed out')),20000);
        worker.onerror = e => { clearTimeout(timeout); reject(new Error(e.message)); };
        worker.onmessage = async ({data}) => {
          statuses.push({type:data.type,status:data.status,diagnostic:data.diagnostic});
          if(data.type==='error') { clearTimeout(timeout); reject(new Error(data.message)); }
          if(data.type==='ready') {
            const canvas = new OffscreenCanvas(640,480);
            canvas.getContext('2d').fillRect(0,0,640,480);
            const image = await createImageBitmap(canvas);
            worker.postMessage({image,time:performance.now()},[image]);
          }
          if(data.type==='pose') {
            clearTimeout(timeout);
            resolve({statuses,body:data.landmarks.length,hands:data.hands.length,present:data.data.present,
              result:statuses.some(m=>m.type==='hands_status'&&m.status==='ready')?'PASSED':'FAILED'});
          }
        };
        worker.postMessage({type:'init'});
      });
    } finally { worker.terminate(); }
  });
}
