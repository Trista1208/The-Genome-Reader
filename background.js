(() => {
  const canvas = document.getElementById("background-canvas");
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false });

  if (!gl) {
    canvas.style.background = "radial-gradient(circle at 50% 48%, #161616 0%, #080808 45%, #000 78%)";
    return;
  }

  const vertexSource = `
    attribute vec2 position;
    void main() {
      gl_Position = vec4(position, 0.0, 1.0);
    }
  `;

  const fragmentSource = `
    precision highp float;
    uniform vec2 uResolution;
    uniform float uTime;

    float random(vec2 point) {
      return fract(sin(dot(point, vec2(12.9898, 78.233))) * 43758.5453123);
    }

    void main() {
      vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution.xy) / min(uResolution.x, uResolution.y);

      vec2 mosaic = vec2(3.0, 2.0);
      vec2 raster = vec2(180.0, 180.0);
      uv.x = floor(uv.x * raster.x / mosaic.x) / (raster.x / mosaic.x);
      uv.y = floor(uv.y * raster.y / mosaic.y) / (raster.y / mosaic.y);

      float radius = length(uv * vec2(0.92, 1.0));
      float time = uTime * 0.055 + random(vec2(floor(uv.x * 28.0), 0.0)) * 0.025;
      float lines = 0.0;

      for (int i = 0; i < 7; i++) {
        float cycle = fract(time + float(i) * 0.095);
        float distanceToLine = abs(cycle * 1.45 - radius);
        lines += 0.00042 * float(i + 1) / (distanceToLine + 0.012);
      }

      lines = clamp(lines, 0.0, 0.085);
      float centerFade = smoothstep(0.08, 0.42, radius);
      float edgeFade = 1.0 - smoothstep(0.78, 1.42, radius);
      float vignette = 1.0 - smoothstep(0.42, 1.55, radius);
      float grain = (random(gl_FragCoord.xy + uTime) - 0.5) * 0.004;

      float value = 0.004 + lines * centerFade * edgeFade + grain;
      value *= 0.48 + vignette * 0.52;
      gl_FragColor = vec4(vec3(max(value, 0.0)), 1.0);
    }
  `;

  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.warn(gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  const vertex = compile(gl.VERTEX_SHADER, vertexSource);
  const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
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

  const resolution = gl.getUniformLocation(program, "uResolution");
  const time = gl.getUniformLocation(program, "uTime");

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.1);
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lastFrame = 0;

  function render(now) {
    if (now - lastFrame >= 1000 / 24 || reducedMotion) {
      lastFrame = now;
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, now * .001);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    if (!reducedMotion) requestAnimationFrame(render);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(render);
})();
