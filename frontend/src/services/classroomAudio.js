export class ClassroomAudio {
  constructor(send, onLevel) {
    this.send = send;
    this.onLevel = onLevel;
    this.nodes = new Set();
    this.cancelled = new Set();
    this.reply = null;
    this.endAt = 0;
    this.timer = null;
    this.lastSpeech = performance.now();
  }
  async start() {
    this.ctx = new AudioContext();
    await this.ctx.resume();
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    if (this.disposed) {
      this.stream.getTracks().forEach((t) => t.stop());
      throw new Error("Audio disposed");
    }
    await this.ctx.audioWorklet.addModule("/classroom-audio.js");
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.capture = new AudioWorkletNode(this.ctx, "classroom-pcm");
    this.capture.port.onmessage = ({ data }) => {
      if (data.flushed) {
        this.flushed?.();
        return;
      }
      const bytes = new Uint8Array(data);
      let binary = "";
      bytes.forEach((b) => {
        binary += String.fromCharCode(b);
      });
      this.send("audio", { audio: btoa(binary) });
    };
    this.source.connect(this.capture);
    this.capture.connect(this.ctx.destination);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.connect(this.ctx.destination);
    this.levelTimer = setInterval(() => {
      const values = new Uint8Array(256);
      this.analyser.getByteTimeDomainData(values);
      this.onLevel(
        Math.min(
          1,
          Math.sqrt(
            values.reduce((a, b) => a + ((b - 128) / 128) ** 2, 0) /
              values.length,
          ) * 5,
        ),
      );
    }, 60);
  }
  chunk(id, encoded, rate = 24000) {
    if (!this.ctx || this.cancelled.has(id)) return;
    if (id !== this.reply) {
      this.reply = id;
      this.endAt = this.ctx.currentTime + 0.06;
      this.first = true;
    }
    const raw = Uint8Array.from(atob(encoded), (x) => x.charCodeAt(0));
    const view = new DataView(raw.buffer);
    const buffer = this.ctx.createBuffer(1, Math.floor(raw.length / 2), rate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++)
      samples[i] = view.getInt16(i * 2, true) / 32768;
    const node = this.ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(this.analyser);
    const start = Math.max(this.ctx.currentTime + 0.01, this.endAt);
    if (this.first) {
      this.send("playback_started", {
        reply_id: id,
        latency_ms: Math.round(
          performance.now() -
            this.lastSpeech +
            (start - this.ctx.currentTime) * 1000,
        ),
      });
      this.first = false;
    }
    node.start(start);
    this.endAt = start + buffer.duration;
    this.nodes.add(node);
    node.onended = () => {
      this.nodes.delete(node);
      node.disconnect();
    };
  }
  end(id, ok = true) {
    clearTimeout(this.timer);
    this.timer = setTimeout(
      () => {
        if (!this.cancelled.has(id))
          this.send(
            ok && this.reply === id ? "playback_done" : "playback_failed",
            { reply_id: id },
          );
      },
      this.ctx
        ? Math.max(0, this.endAt - this.ctx.currentTime) * 1000 + 100
        : 0,
    );
  }
  cancel(id) {
    if (id) this.cancelled.add(id);
    clearTimeout(this.timer);
    this.nodes.forEach((n) => {
      try {
        n.stop();
      } catch {}
    });
    this.nodes.clear();
    this.reply = null;
    this.endAt = 0;
    this.onLevel(0);
  }
  async stopCapture(flush = false) {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.source?.disconnect();
    if (flush && this.capture)
      await new Promise((resolve) => {
        this.flushed = resolve;
        this.capture.port.postMessage("flush");
        setTimeout(resolve, 250);
      });
    this.capture?.disconnect();
  }
  async close() {
    this.disposed = true;
    await this.stopCapture();
    this.cancel(this.reply);
    clearInterval(this.levelTimer);
    await this.ctx?.close().catch(() => {});
  }
}
