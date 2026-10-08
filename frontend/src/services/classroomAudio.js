export const STUDENT_PLAYBACK_RATE = 1.2;

export class ClassroomAudio {
  constructor(send, onLevel, onPlayback = () => {}, { playbackRate = STUDENT_PLAYBACK_RATE } = {}) {
    this.playbackRate = playbackRate;
    this.send = send;
    this.onLevel = onLevel;
    this.onPlayback = onPlayback;
    this.nodes = new Set();
    this.cancelled = new Set();
    this.reply = null;
    this.endAt = 0;
    this.timer = null;
    this.lastSpeech = performance.now();
    this.volume = 1;
  }
  setVolume(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return;
    this.volume = Math.max(0, Math.min(1, value));
    this.outputGain?.gain.setTargetAtTime(this.volume, this.ctx.currentTime, .02);
  }
  recordingStream() {
    if (!this.ctx || this.disposed) return null;
    if (!this.recordDestination) {
      this.recordDestination = this.ctx.createMediaStreamDestination();
      this.source.connect(this.recordDestination);
      // Tap the actual playback gain, never feed mixed student audio into ASR.
      this.outputGain.connect(this.recordDestination);
    }
    return this.recordDestination.stream;
  }
  async start() {
    this.ctx = new AudioContext();
    await this.ctx.resume();
    if (this.disposed) throw new Error("Audio disposed");
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
    if (this.disposed) {
      this.stream.getTracks().forEach((t) => t.stop());
      throw new Error("Audio disposed");
    }
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
    this.outputGain = this.ctx.createGain();
    this.outputGain.gain.value = this.volume;
    this.outputGain.connect(this.analyser);
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
    if (this.disposed || !this.ctx || this.cancelled.has(id)) return;
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
    node.playbackRate.value = this.playbackRate;
    node.connect(this.outputGain);
    const start = Math.max(this.ctx.currentTime + 0.01, this.endAt);
    if (this.first) {
      clearTimeout(this.playingTimer);
      this.playingTimer = setTimeout(
        () => {
          if (!this.disposed && !this.cancelled.has(id) && this.reply === id)
            this.onPlayback(id, "playing");
        },
        Math.max(0, start - this.ctx.currentTime) * 1000,
      );
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
    // Buffers retain the provider's sample rate; only student playback runs faster.
    this.endAt = start + buffer.duration / this.playbackRate;
    this.nodes.add(node);
    node.onended = () => {
      this.nodes.delete(node);
      node.disconnect();
    };
  }
  end(id, ok = true) {
    if (
      this.disposed ||
      this.cancelled.has(id) ||
      (this.reply && this.reply !== id)
    )
      return;
    clearTimeout(this.timer);
    this.timer = setTimeout(
      () => {
        if (!this.disposed && !this.cancelled.has(id)) {
          // Terminal replies must not be replayed or acknowledge completion twice.
          this.cancelled.add(id);
          this.onPlayback(id, ok && this.reply === id ? "done" : "failed");
          this.send(
            ok && this.reply === id ? "playback_done" : "playback_failed",
            { reply_id: id },
          );
          if (this.reply === id) this.reply = null;
        }
      },
      this.ctx
        ? Math.max(0, this.endAt - this.ctx.currentTime) * 1000 + 100
        : 0,
    );
  }
  cancel(id) {
    if (id) this.cancelled.add(id);
    if (id && this.reply && id !== this.reply) return;
    clearTimeout(this.timer);
    clearTimeout(this.playingTimer);
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
