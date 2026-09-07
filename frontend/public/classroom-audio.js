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
          const pcm = new Int16Array(this.samples);
          this.port.postMessage(pcm.buffer, [pcm.buffer]);
          this.samples = [];
        }
        this.port.postMessage({ flushed: true });
      }
    };
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
        const pcm = new Int16Array(this.samples);
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
        this.samples = [];
      }
    }
    // Never send microphone sound back to speakers.
    outputs[0]?.forEach((channel) => channel.fill(0));
    return true;
  }
}
registerProcessor("classroom-pcm", ClassroomPCM);
