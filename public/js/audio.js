/* Tiny procedural soundscape built with the Web Audio API. No assets needed. */

export class SoundEngine {
  constructor(enabled = true) {
    this.enabled = enabled;
    this.ctx = null;
    this.master = null;
    this.noiseBuffer = null;
    this.lastPlayed = new Map();
  }

  unlock() {
    if (!this.enabled) return;
    const ctx = this.ensure();
    if (ctx && ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (this.master && this.ctx) {
      const now = this.ctx.currentTime;
      this.master.gain.cancelScheduledValues(now);
      this.master.gain.setTargetAtTime(enabled ? 0.32 : 0.0001, now, 0.03);
    }
    if (enabled) this.unlock();
  }

  ensure() {
    if (this.ctx) return this.ctx;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    try {
      this.ctx = new AudioContextClass();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.enabled ? 0.32 : 0.0001;
      this.master.connect(this.ctx.destination);
      this.noiseBuffer = this.makeNoise();
      return this.ctx;
    } catch {
      this.ctx = null;
      return null;
    }
  }

  makeNoise() {
    const length = Math.floor(this.ctx.sampleRate * 0.9);
    const buffer = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }

  throttle(key, ms) {
    const now = performance.now();
    if ((this.lastPlayed.get(key) || 0) + ms > now) return true;
    this.lastPlayed.set(key, now);
    return false;
  }

  tone(freq, duration, options = {}) {
    if (!this.ctx) return;
    const {
      endFreq = freq,
      type = "sine",
      gain = 0.08,
      delay = 0,
      attack = 0.008,
    } = options;
    const ctx = this.ctx;
    const start = ctx.currentTime + delay;
    const oscillator = ctx.createOscillator();
    const envelope = ctx.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(Math.max(20, freq), start);
    oscillator.frequency.exponentialRampToValueAtTime(
      Math.max(20, endFreq),
      start + duration,
    );
    envelope.gain.setValueAtTime(0.0001, start);
    envelope.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain), start + attack);
    envelope.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(envelope);
    envelope.connect(this.master);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
  }

  noise(duration, options = {}) {
    if (!this.ctx || !this.noiseBuffer) return;
    const { gain = 0.06, frequency = 1200, q = 0.8, delay = 0 } = options;
    const ctx = this.ctx;
    const start = ctx.currentTime + delay;
    const source = ctx.createBufferSource();
    source.buffer = this.noiseBuffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(frequency, start);
    filter.Q.value = q;
    const envelope = ctx.createGain();
    envelope.gain.setValueAtTime(gain, start);
    envelope.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    source.connect(filter);
    filter.connect(envelope);
    envelope.connect(this.master);
    source.start(start);
    source.stop(start + duration);
  }

  play(name) {
    if (!this.enabled) return;
    const ctx = this.ensure();
    if (!ctx || ctx.state === "suspended") return;
    if (this.throttle(name, 45)) return;

    switch (name) {
      case "fire":
        this.noise(0.22, { gain: 0.05, frequency: 720, q: 0.5 });
        this.tone(240, 0.24, { endFreq: 72, type: "sine", gain: 0.075 });
        break;
      case "frost":
        this.tone(880, 0.24, { endFreq: 420, type: "triangle", gain: 0.055 });
        this.tone(1320, 0.18, { endFreq: 700, type: "sine", gain: 0.03, delay: 0.02 });
        this.noise(0.16, { gain: 0.025, frequency: 3400, q: 1.4 });
        break;
      case "cast":
        this.tone(520, 0.2, { endFreq: 900, type: "sine", gain: 0.035 });
        break;
      case "impact":
        if (this.throttle("impact-soft", 80)) return;
        this.noise(0.12, { gain: 0.028, frequency: 460, q: 0.7 });
        this.tone(120, 0.12, { endFreq: 60, gain: 0.025 });
        break;
      case "hit":
        if (this.throttle("hit-soft", 65)) return;
        this.tone(96, 0.16, { endFreq: 44, type: "sine", gain: 0.1 });
        this.noise(0.11, { gain: 0.055, frequency: 320, q: 0.5 });
        break;
      case "hurt":
        if (this.throttle("hurt", 110)) return;
        this.tone(74, 0.3, { endFreq: 38, type: "sawtooth", gain: 0.095 });
        this.noise(0.2, { gain: 0.07, frequency: 240, q: 0.4 });
        break;
      case "death":
        this.tone(220, 0.8, { endFreq: 35, type: "sine", gain: 0.12 });
        this.tone(110, 0.9, { endFreq: 28, type: "triangle", gain: 0.07, delay: 0.06 });
        this.noise(0.45, { gain: 0.06, frequency: 160, q: 0.4 });
        break;
      case "heal":
        [392, 523, 659].forEach((freq, index) => {
          this.tone(freq, 0.55, {
            endFreq: freq * 1.02,
            type: "sine",
            gain: 0.045,
            delay: index * 0.065,
          });
        });
        break;
      case "shield":
        this.tone(280, 0.55, { endFreq: 520, type: "sine", gain: 0.05 });
        this.tone(840, 0.65, { endFreq: 900, type: "triangle", gain: 0.025, delay: 0.04 });
        this.noise(0.3, { gain: 0.018, frequency: 2600, q: 1.8 });
        break;
      case "nova":
        this.tone(80, 0.55, { endFreq: 32, type: "sine", gain: 0.14 });
        this.tone(440, 0.4, { endFreq: 90, type: "sawtooth", gain: 0.045 });
        this.noise(0.4, { gain: 0.07, frequency: 520, q: 0.5 });
        break;
      case "beam":
        this.tone(72, 0.5, { endFreq: 46, type: "sawtooth", gain: 0.11 });
        this.tone(520, 0.38, { endFreq: 140, type: "square", gain: 0.035 });
        this.noise(0.42, { gain: 0.065, frequency: 1800, q: 1.2 });
        break;
      case "dash":
        this.noise(0.22, { gain: 0.055, frequency: 1050, q: 0.5 });
        this.tone(180, 0.18, { endFreq: 520, type: "triangle", gain: 0.025 });
        break;
      case "roll":
        this.noise(0.18, { gain: 0.05, frequency: 620, q: 0.45 });
        this.tone(150, 0.2, { endFreq: 290, type: "triangle", gain: 0.028 });
        break;
      case "chain":
        this.noise(0.28, { gain: 0.07, frequency: 3200, q: 0.9 });
        this.tone(880, 0.2, { endFreq: 220, type: "sawtooth", gain: 0.045 });
        this.tone(1320, 0.14, { endFreq: 440, type: "square", gain: 0.022, delay: 0.035 });
        break;
      case "lightning":
        this.noise(0.34, { gain: 0.095, frequency: 5200, q: 0.75 });
        this.tone(96, 0.58, { endFreq: 30, type: "sawtooth", gain: 0.13 });
        this.tone(1860, 0.18, { endFreq: 240, type: "square", gain: 0.028 });
        this.tone(620, 0.32, { endFreq: 120, type: "sawtooth", gain: 0.04, delay: 0.03 });
        break;
      case "meteor":
        this.tone(54, 0.9, { endFreq: 92, type: "sawtooth", gain: 0.05 });
        this.noise(0.65, { gain: 0.035, frequency: 420, q: 0.6 });
        break;
      case "meteor_impact":
        this.tone(58, 0.8, { endFreq: 24, type: "sawtooth", gain: 0.16 });
        this.tone(180, 0.5, { endFreq: 48, type: "square", gain: 0.06 });
        this.noise(0.6, { gain: 0.095, frequency: 520, q: 0.55 });
        break;
      case "siphon":
        this.tone(260, 0.45, { endFreq: 620, type: "triangle", gain: 0.05 });
        this.noise(0.35, { gain: 0.035, frequency: 760, q: 1.2 });
        break;
      case "poison":
        this.noise(0.55, { gain: 0.04, frequency: 680, q: 0.7 });
        this.tone(160, 0.45, { endFreq: 110, type: "triangle", gain: 0.025 });
        break;
      case "poison_tick":
        if (this.throttle("poison-tick", 150)) return;
        this.noise(0.16, { gain: 0.025, frequency: 420, q: 0.7 });
        this.tone(190, 0.14, { endFreq: 120, type: "sine", gain: 0.018 });
        break;
      case "cloud_fade":
        this.tone(220, 0.32, { endFreq: 90, type: "sine", gain: 0.018 });
        break;
      case "emp":
        this.tone(90, 0.7, { endFreq: 180, type: "sawtooth", gain: 0.04 });
        this.tone(440, 0.55, { endFreq: 880, type: "sine", gain: 0.028 });
        this.noise(0.5, { gain: 0.025, frequency: 2400, q: 1.6 });
        break;
      case "emp_pull":
        this.tone(360, 0.42, { endFreq: 72, type: "sine", gain: 0.065 });
        this.tone(980, 0.32, { endFreq: 180, type: "triangle", gain: 0.028 });
        this.noise(0.36, { gain: 0.04, frequency: 920, q: 1.5 });
        break;
      case "emp_blast":
        this.tone(62, 0.75, { endFreq: 28, type: "sawtooth", gain: 0.14 });
        this.tone(240, 0.5, { endFreq: 70, type: "square", gain: 0.045 });
        this.noise(0.55, { gain: 0.08, frequency: 680, q: 0.6 });
        break;
      case "ward":
        this.tone(330, 0.42, { endFreq: 660, type: "triangle", gain: 0.045 });
        this.tone(660, 0.35, { endFreq: 990, type: "sine", gain: 0.025, delay: 0.08 });
        break;
      case "ward_blast":
        if (this.throttle("ward-blast", 100)) return;
        this.tone(140, 0.44, { endFreq: 42, type: "sine", gain: 0.12 });
        this.noise(0.34, { gain: 0.06, frequency: 760, q: 0.7 });
        break;
      case "ward_fade":
        this.tone(520, 0.32, { endFreq: 160, type: "sine", gain: 0.022 });
        break;
      case "respawn":
        [262, 392, 523, 784].forEach((freq, index) => {
          this.tone(freq, 0.7, {
            endFreq: freq * 1.01,
            gain: 0.032,
            delay: index * 0.07,
            type: "sine",
          });
        });
        break;
      case "error":
        this.tone(150, 0.18, { endFreq: 105, type: "square", gain: 0.032 });
        break;
      case "click":
        this.tone(680, 0.06, { endFreq: 480, type: "triangle", gain: 0.022 });
        break;
      case "join":
        [220, 330, 440, 660].forEach((freq, index) => {
          this.tone(freq, 0.8, {
            endFreq: freq,
            gain: 0.028,
            delay: index * 0.075,
            type: "sine",
            attack: 0.05,
          });
        });
        break;
      case "death-near":
        this.tone(98, 0.7, { endFreq: 38, type: "sine", gain: 0.09 });
        break;
      default:
        break;
    }
  }
}
