<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { Color, Mesh, Program, Renderer, Triangle } from "ogl";

defineOptions({ inheritAttrs: false });

const props = defineProps({
  disabled: { type: Boolean, default: false },
  type: { type: String, default: "button" },
  radius: { type: Number, default: 10 },
  lineColor: { type: String, default: "#fff3e8" },
  baseColor: { type: String, default: "#6b2e12" },
  intensity: { type: Number, default: 1.15 },
  shineSize: { type: Number, default: 12 },
  shineFade: { type: Number, default: 38 },
  thickness: { type: Number, default: 1.15 },
  speed: { type: Number, default: 0.28 },
  proximity: { type: Number, default: 220 },
});

defineEmits(["click"]);

const buttonRef = ref(null);
const effectRef = ref(null);
const PAD = 20;

const VERTEX_SHADER = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform vec2 uCenter;
uniform vec2 uHalfSize;
uniform float uRadius;
uniform float uAngle;
uniform float uPx;
uniform vec3 uLineColor;
uniform vec3 uBaseColor;
uniform float uIntensity;
uniform float uShineSize;
uniform float uShineFade;
uniform float uThickness;
uniform float uBaseWidth;

out vec4 fragColor;

float sdRoundedRect(vec2 p, vec2 b, float r) {
  vec2 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float gaussianLine(float d, float sigma) {
  float x = d / (sigma + 1e-6);
  float k = mix(1.0, 1.6, smoothstep(0.0, 1.5, x));
  return exp(-k * x * x);
}

void main() {
  vec2 p = gl_FragCoord.xy - uCenter;
  float d = sdRoundedRect(p, uHalfSize, uRadius);
  vec2 light = vec2(cos(uAngle), sin(uAngle));
  float base = (1.0 - smoothstep(0.0, uBaseWidth, abs(d))) * 0.4;
  vec2 normal = normalize(p / (uHalfSize * uHalfSize) + 1e-6);
  float phi = acos(clamp(abs(dot(normal, light)), 0.0, 1.0));
  float rim = 1.0 - smoothstep(
    uShineSize - uShineFade,
    uShineSize + uShineFade + 1e-4,
    phi
  );
  float line = gaussianLine(d, uThickness);
  float edgeClamp = 1.0 - smoothstep(0.5 * uPx, 3.0 * uPx, abs(d));
  float highlight = line * rim * edgeClamp * uIntensity;
  vec3 color = uBaseColor * base + uLineColor * highlight;
  fragColor = vec4(color, clamp(base + highlight, 0.0, 1.0));
}
`;

let cleanup = () => {};

onMounted(() => {
  const button = buttonRef.value;
  const effect = effectRef.value;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!button || !effect || reduceMotion.matches) return;

  let renderer;
  try {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer = new Renderer({
      alpha: true,
      premultipliedAlpha: true,
      antialias: true,
      dpr,
    });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    const geometry = new Triangle(gl);
    if (geometry.attributes.uv) delete geometry.attributes.uv;
    const program = new Program(gl, {
      vertex: VERTEX_SHADER,
      fragment: FRAGMENT_SHADER,
      uniforms: {
        uCenter: { value: [0, 0] },
        uHalfSize: { value: [1, 1] },
        uRadius: { value: 0 },
        uAngle: { value: 2.4 },
        uPx: { value: dpr },
        uLineColor: { value: [1, 1, 1] },
        uBaseColor: { value: [0.42, 0.18, 0.07] },
        uIntensity: { value: 0 },
        uShineSize: { value: 0.2 },
        uShineFade: { value: 0.66 },
        uThickness: { value: dpr },
        uBaseWidth: { value: dpr },
      },
    });
    const mesh = new Mesh(gl, { geometry, program });
    effect.appendChild(gl.canvas);

    const size = { width: 1, height: 1 };
    const resize = () => {
      const rect = button.getBoundingClientRect();
      size.width = rect.width;
      size.height = rect.height;
      renderer.setSize(rect.width + PAD * 2, rect.height + PAD * 2);
      program.uniforms.uCenter.value = [
        (PAD + rect.width / 2) * dpr,
        (PAD + rect.height / 2) * dpr,
      ];
      program.uniforms.uHalfSize.value = [
        (rect.width / 2) * dpr,
        (rect.height / 2) * dpr,
      ];
    };
    const observer = new ResizeObserver(resize);
    observer.observe(button);
    resize();

    let pointerAngle = null;
    let proximityAmount = 0;
    const handlePointerMove = (event) => {
      const rect = button.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const distanceX = Math.max(
        rect.left - event.clientX,
        0,
        event.clientX - rect.right,
      );
      const distanceY = Math.max(
        rect.top - event.clientY,
        0,
        event.clientY - rect.bottom,
      );
      const distance = Math.hypot(distanceX, distanceY);
      if (distance === 0) {
        const x = (event.clientX - centerX) / (rect.width / 2);
        const y = (centerY - event.clientY) / (rect.height / 2);
        pointerAngle =
          Math.atan2(2 / rect.height, -2 / rect.width) + x * 0.3 + y * 0.15;
      } else {
        pointerAngle = Math.atan2(centerY - event.clientY, event.clientX - centerX);
      }
      const amount = Math.max(0, 1 - distance / Math.max(props.proximity, 1));
      proximityAmount = amount * amount * (3 - 2 * amount);
    };
    window.addEventListener("pointermove", handlePointerMove, { passive: true });

    let angle = 2.4;
    let idleAngle = 2.4;
    let brightness = 0;
    let previous = performance.now();
    let frame = 0;
    const line = new Color();
    const base = new Color();
    const draw = (now) => {
      frame = requestAnimationFrame(draw);
      const delta = Math.min((now - previous) / 1000, 0.05);
      previous = now;
      idleAngle += props.speed * delta;
      const target = pointerAngle ?? idleAngle;
      const difference =
        ((target - angle + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
      angle += difference * (1 - Math.exp(-delta * 7));
      brightness +=
        (proximityAmount - brightness) * (1 - Math.exp(-delta * 8));

      line.set(props.lineColor);
      base.set(props.baseColor);
      program.uniforms.uAngle.value = angle;
      program.uniforms.uRadius.value =
        Math.min(props.radius, Math.min(size.width, size.height) / 2) * dpr;
      program.uniforms.uLineColor.value = [line.r, line.g, line.b];
      program.uniforms.uBaseColor.value = [base.r, base.g, base.b];
      program.uniforms.uIntensity.value = props.intensity * brightness;
      program.uniforms.uShineSize.value = (props.shineSize * Math.PI) / 180;
      program.uniforms.uShineFade.value = (props.shineFade * Math.PI) / 180;
      program.uniforms.uThickness.value = props.thickness * dpr;
      renderer.render({ scene: mesh });
    };
    frame = requestAnimationFrame(draw);

    cleanup = () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("pointermove", handlePointerMove);
      gl.canvas.remove();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  } catch {
    renderer?.gl?.canvas?.remove();
  }
});

onBeforeUnmount(() => cleanup());
</script>

<template>
  <button
    ref="buttonRef"
    v-bind="$attrs"
    :type="type"
    :disabled="disabled"
    class="specular-button"
    :style="{ '--specular-radius': `${radius}px` }"
    @click="$emit('click', $event)"
  >
    <span ref="effectRef" class="specular-button__effect" aria-hidden="true" />
    <span class="specular-button__label"><slot /></span>
  </button>
</template>

<style scoped>
.specular-button {
  position: relative;
  isolation: isolate;
  overflow: visible;
  touch-action: manipulation;
}

.specular-button__effect {
  position: absolute;
  z-index: 1;
  inset: -20px;
  overflow: visible;
  border-radius: calc(var(--specular-radius) + 20px);
  pointer-events: none;
}

.specular-button__effect :deep(canvas) {
  display: block;
}

.specular-button__label {
  position: relative;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: inherit;
  white-space: nowrap;
}

.specular-button:not(:disabled):active {
  transform: translateY(1px);
}

@media (prefers-reduced-motion: reduce) {
  .specular-button__effect {
    display: none;
  }
}
</style>
