(() => {
  const canvas = document.getElementById("background-canvas");
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false });

  if (!gl) {
    canvas.style.background = "radial-gradient(circle at 45% 45%, #232323 0%, #0b0b0b 48%, #000 100%)";
    return;
  }

  const vertexSource = `
    attribute vec2 position;
    varying vec2 vUv;
    void main() {
      vUv = position * 0.5 + 0.5;
      gl_Position = vec4(position, 0.0, 1.0);
    }
  `;

  const fragmentSource = `
    precision highp float;
    varying vec2 vUv;

    uniform vec2 uResolution;
    uniform float uTime;
    uniform float uGrain;
    uniform vec3 uColors[3];

    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

    float snoise(vec2 v) {
      const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
      vec2 i = floor(v + dot(v, C.yy));
      vec2 x0 = v - i + dot(i, C.xx);
      vec2 i1 = x0.x > x0.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod289(i);
      vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
      vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
      m = m * m;
      m = m * m;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
      vec3 g;
      g.x = a0.x * x0.x + h.x * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    void main() {
      vec2 uv = vUv;
      float ratio = uResolution.x / uResolution.y;
      vec2 p = uv * vec2(ratio, 1.0);
      float t = uTime * 0.2;
      float n1 = snoise(p * 0.52 + t);
      float n2 = snoise(p * 0.94 - t * 0.48 + n1 * 0.72);
      float ridge = pow(abs(n2), 2.7);

      vec3 color = vec3(0.002);
      color += uColors[0] * smoothstep(0.02, 0.9, n1) * 0.34;
      color += uColors[1] * ridge * 0.22;
      color += uColors[2] * smoothstep(0.64, 1.0, ridge) * 0.08;

      float grain = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + uTime);
      color += (grain - 0.5) * uGrain;
      float vignette = 1.0 - smoothstep(0.2, 0.82, length(uv - 0.5));
      color *= 0.24 + vignette * 0.52;
      gl_FragColor = vec4(color, 1.0);
    }
  `;

  function shader(type, source) {
    const compiled = gl.createShader(type);
    gl.shaderSource(compiled, source);
    gl.compileShader(compiled);
    if (!gl.getShaderParameter(compiled, gl.COMPILE_STATUS)) {
      console.warn(gl.getShaderInfoLog(compiled));
      gl.deleteShader(compiled);
      return null;
    }
    return compiled;
  }

  const vertex = shader(gl.VERTEX_SHADER, vertexSource);
  const fragment = shader(gl.FRAGMENT_SHADER, fragmentSource);
  if (!vertex || !fragment) return;

  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "position");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

  const uniforms = {
    resolution: gl.getUniformLocation(program, "uResolution"),
    time: gl.getUniformLocation(program, "uTime"),
    grain: gl.getUniformLocation(program, "uGrain"),
    colors: gl.getUniformLocation(program, "uColors"),
  };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lastFrame = 0;

  function render(now) {
    if (now - lastFrame >= 1000 / 30 || reducedMotion) {
      lastFrame = now;
      gl.uniform2f(uniforms.resolution, canvas.width, canvas.height);
      gl.uniform1f(uniforms.time, now * .00016);
      gl.uniform1f(uniforms.grain, .006);
      gl.uniform3fv(uniforms.colors, new Float32Array([
        .035, .035, .04,
        .075, .075, .08,
        .14, .14, .15,
      ]));
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    if (!reducedMotion) requestAnimationFrame(render);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(render);
})();
