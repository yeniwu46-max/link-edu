// One MediaPipe task per module worker; bounded requests and independent recovery.
export class MotionTaskClient {
  constructor(factory, status) { this.factory = factory; this.status = status; this.ready = false; }
  stop() {
    this.ready = false;
    this.pending?.reject(new Error('Motion task stopped'));
    this.pending = null;
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.worker = null;
  }
  request(message, transfer = [], timeout = 1500) {
    return new Promise((resolve, reject) => {
      if (!this.worker || this.pending) return reject(new Error('Motion task unavailable'));
      const pending = {resolve, reject};
      this.pending = pending;
      this.timer = setTimeout(() => {
        if (this.pending === pending) { this.pending = null; reject(new Error('Motion task timed out')); }
      }, timeout);
      try { this.worker.postMessage(message, transfer); }
      catch (error) { clearTimeout(this.timer); this.pending = null; reject(error); }
    });
  }
  async start() {
    this.stop(); this.status('loading');
    let worker = null;
    try {
      worker = this.worker = this.factory();
      worker.onmessage = ({data}) => {
        if (worker !== this.worker || !this.pending) return;
        const pending = this.pending; this.pending = null; clearTimeout(this.timer);
        if (data.type === 'error') pending.reject(new Error('Motion task failed'));
        else pending.resolve(data);
      };
      worker.onerror = () => { if (worker === this.worker) { this.stop(); this.status('failed'); } };
      await this.request({type: 'init'}, [], 10000);
      if (worker !== this.worker) return;
      this.ready = true; this.status('ready');
    } catch { if (worker === this.worker) { this.stop(); this.status('failed'); } }
  }
  async frame(image, time) {
    if (!this.ready) return null;
    const worker = this.worker;
    let copy;
    try {
      copy = await createImageBitmap(image);
      if (worker !== this.worker) { copy.close(); return null; }
      return await this.request({image: copy, time}, [copy]);
    } catch {
      copy?.close();
      if (worker === this.worker) { this.stop(); this.status('failed'); }
      return null;
    }
  }
}
