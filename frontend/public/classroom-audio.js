class ClassroomPCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.samples = [];
    this.phase = 0;
    this.sum = 0;
    this.n = 0;
    this.port.onmessage = ({ data }) => {
      if (data === "flush") {
        if (this.samples.length) {
          this.flushSamples();
          this.samples = [];
        }
        this.port.postMessage({ flushed: true });
      }
    };
  }
  flushSamples() {
    const pcm = new Int16Array(this.samples);
    let square = 0;
    let crossings = 0;
    for (let i = 0; i < pcm.length; i++) {
      const value = pcm[i] / 32768;
      square += value * value;
      if (i && (pcm[i - 1] < 0) !== (pcm[i] < 0)) crossings++;
    }
    const rms = Math.sqrt(square / Math.max(1, pcm.length));
    // Decimated autocorrelation gives a lightweight pitch-period estimate for voiced frames.
    const decimated = [];
    for (let i = 0; i < pcm.length; i += 2) decimated.push(pcm[i] / 32768);
    const minLag = 20; // 400 Hz at 8 kHz
    const maxLag = 133; // about 60 Hz at 8 kHz
    let bestLag = 0, best = 0;
    for (let lag = minLag; lag <= Math.min(maxLag, decimated.length / 2); lag++) {
      let corr = 0, left = 0, right = 0;
      for (let i = 0; i < decimated.length - lag; i++) {
        const a = decimated[i], b = decimated[i + lag];
        corr += a * b; left += a * a; right += b * b;
      }
      const score = corr / Math.sqrt((left * right) || 1);
      if (score > best) { best = score; bestLag = lag; }
    }
    const pitchHz = best >= 0.55 && bestLag ? Math.round(8000 / bestLag) : null;
    this.port.postMessage({
      pcm: pcm.buffer,
      features: {
        rms_dbfs: Math.round(20 * Math.log10(Math.max(rms, 1e-5)) * 10) / 10,
        zero_crossing_rate: Math.round(crossings / Math.max(1, pcm.length - 1) * 1000) / 1000,
        pitch_hz: pitchHz,
      },
    }, [pcm.buffer]);
  }
  process(inputs, outputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    const ratio = sampleRate / 16000;
    for (const sample of channel) {
      this.sum += sample;
      this.n++;
      this.phase++;
      if (this.phase >= ratio) {
        this.samples.push(
          Math.round(Math.max(-1, Math.min(1, this.sum / this.n)) * 32767),
        );
        this.sum = 0;
        this.n = 0;
        this.phase -= ratio;
      }
      if (this.samples.length >= 3200) {
        this.flushSamples();
        this.samples = [];
      }
    }
    // Never send microphone sound back to speakers.
    outputs[0]?.forEach((channel) => channel.fill(0));
    return true;
  }
}
registerProcessor("classroom-pcm", ClassroomPCM);
