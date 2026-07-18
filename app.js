(() => {
  const canvas = document.getElementById("sequence-canvas");
  const context = canvas.getContext("2d");
  const story = document.getElementById("scroll-story");
  const railFill = document.getElementById("rail-fill");
  const railCurrent = document.getElementById("rail-current");
  const railStages = [...document.querySelectorAll(".rail-stage")];
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const LOOP_DURATION = 15;
  const SCROLL_START_TIME = .75;
  const SCROLL_END_TIME = 14.2;
  const SPIN_END = 5.1;
  const SHIFT_END = 7;
  const TOKEN_END = 9.35;
  const NETWORK_START = 8.25;
  const WHITE = "248,248,246";
  const DNA_SEGMENTS = 39;
  const NETWORK_COUNTS = [12, 11, 10, 8, 6, 2];
  const requestedTime = Number(new URLSearchParams(window.location.search).get("t"));
  const isFrozenPreview = Number.isFinite(requestedTime) && window.location.search.includes("t=");

  let width = 0;
  let height = 0;
  let dpr = 1;
  let elapsed = isFrozenPreview ? normalizeTime(requestedTime) : SCROLL_START_TIME;
  let targetElapsed = elapsed;
  let frameId = null;
  let lastFrame = performance.now();

  const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
  const mod = (value, divisor) => ((value % divisor) + divisor) % divisor;
  const lerp = (from, to, amount) => from + (to - from) * amount;
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };

  function normalizeTime(value) {
    return ((value % LOOP_DURATION) + LOOP_DURATION) % LOOP_DURATION;
  }

  function resize() {
    const bounds = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = bounds.width;
    height = bounds.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function line(from, to, alpha, lineWidth = 1, color = WHITE) {
    if (alpha <= .003) return;
    context.save();
    context.strokeStyle = `rgba(${color},${alpha})`;
    context.lineWidth = lineWidth;
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.restore();
  }

  function pointOnCurve(from, controlA, controlB, to, progress) {
    const t = clamp(progress);
    const inverse = 1 - t;
    return {
      x: inverse ** 3 * from.x + 3 * inverse ** 2 * t * controlA.x + 3 * inverse * t ** 2 * controlB.x + t ** 3 * to.x,
      y: inverse ** 3 * from.y + 3 * inverse ** 2 * t * controlA.y + 3 * inverse * t ** 2 * controlB.y + t ** 3 * to.y,
    };
  }

  function drawTube(from, to, radius, brightness, alpha) {
    if (alpha <= .003) return;
    const value = Math.round(clamp(brightness, 38, 242));
    context.save();
    context.lineCap = "round";
    context.strokeStyle = `rgba(0,0,0,${alpha * .92})`;
    context.lineWidth = radius + 7;
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.strokeStyle = `rgba(${Math.round(value * .34)},${Math.round(value * .34)},${Math.round(value * .34)},${alpha})`;
    context.lineWidth = radius + 3;
    context.stroke();
    context.strokeStyle = `rgba(${value},${value},${Math.min(255, value + 4)},${alpha})`;
    context.lineWidth = radius;
    context.stroke();
    context.strokeStyle = `rgba(255,255,255,${alpha * .34})`;
    context.lineWidth = Math.max(1, radius * .22);
    context.stroke();
    context.restore();
  }

  function drawSphere(position, radius, brightness, alpha) {
    if (alpha <= .003) return;
    const value = Math.round(clamp(brightness, 60, 250));
    const gradient = context.createRadialGradient(
      position.x - radius * .34,
      position.y - radius * .38,
      radius * .08,
      position.x,
      position.y,
      radius,
    );
    gradient.addColorStop(0, `rgba(255,255,255,${alpha})`);
    gradient.addColorStop(.42, `rgba(${value},${value},${value},${alpha})`);
    gradient.addColorStop(1, `rgba(20,20,20,${alpha})`);
    context.save();
    context.fillStyle = gradient;
    context.beginPath();
    context.arc(position.x, position.y, radius, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function projectDna(x, y, z, camera) {
    const cosYaw = Math.cos(camera.yaw);
    const sinYaw = Math.sin(camera.yaw);
    const cosPitch = Math.cos(camera.pitch);
    const sinPitch = Math.sin(camera.pitch);
    const rotatedX = x * cosYaw + z * sinYaw;
    const rotatedZ = -x * sinYaw + z * cosYaw;
    const rotatedY = y * cosPitch - rotatedZ * sinPitch;
    const depth = camera.distance + y * sinPitch + rotatedZ * cosPitch;
    const perspective = 880 / (880 + depth);
    return {
      x: camera.x + rotatedX * perspective,
      y: camera.y + rotatedY * perspective,
      z: depth,
      scale: perspective,
      light: clamp(.52 + rotatedZ / 240, .2, 1),
    };
  }

  function dnaCamera(time) {
    const spin = smooth((time - SCROLL_START_TIME) / (SPIN_END - SCROLL_START_TIME));
    const shift = smooth((time - SPIN_END) / (SHIFT_END - SPIN_END));
    return {
      x: lerp(width * .5, width * .205, shift),
      y: height * .5,
      yaw: -.62 + spin * Math.PI * 2.15,
      pitch: lerp(.08, -.04, shift),
      distance: lerp(590, 820, shift),
      shift,
    };
  }

  function buildDna(time) {
    const camera = dnaCamera(time);
    const radius = Math.min(width, height) * .138;
    const rise = Math.min(width, height) * .041;
    const nodes = [];
    for (let index = 0; index < DNA_SEGMENTS; index += 1) {
      const angle = index * .55;
      const y = (index - (DNA_SEGMENTS - 1) / 2) * rise;
      const strandA = projectDna(Math.cos(angle) * radius, y, Math.sin(angle) * radius, camera);
      const strandB = projectDna(Math.cos(angle + Math.PI) * radius, y, Math.sin(angle + Math.PI) * radius, camera);
      nodes.push({ index, strandA, strandB, middle: { x: (strandA.x + strandB.x) / 2, y: (strandA.y + strandB.y) / 2 } });
    }
    return { nodes, camera };
  }

  function drawRealisticDna(time, alpha) {
    const dna = buildDna(time);
    const primitives = [];
    const extraction = smooth((time - SHIFT_END + .35) / (TOKEN_END - SHIFT_END));

    for (let index = 0; index < dna.nodes.length - 1; index += 1) {
      const current = dna.nodes[index];
      const next = dna.nodes[index + 1];
      primitives.push({ type: "strand", from: current.strandA, to: next.strandA, depth: (current.strandA.z + next.strandA.z) / 2 });
      primitives.push({ type: "strand", from: current.strandB, to: next.strandB, depth: (current.strandB.z + next.strandB.z) / 2 });
    }
    dna.nodes.forEach((node) => primitives.push({ type: "rung", node, depth: (node.strandA.z + node.strandB.z) / 2 }));
    primitives.sort((a, b) => b.depth - a.depth);

    primitives.forEach((primitive) => {
      if (primitive.type === "strand") {
        const scale = (primitive.from.scale + primitive.to.scale) / 2;
        const light = (primitive.from.light + primitive.to.light) / 2;
        drawTube(primitive.from, primitive.to, Math.max(7, 19 * scale), 82 + light * 148, alpha);
        return;
      }
      const { node } = primitive;
      const selected = node.index % 3 === 1;
      const rungAlpha = selected ? alpha * (1 - extraction * .82) : alpha;
      const scale = (node.strandA.scale + node.strandB.scale) / 2;
      const light = (node.strandA.light + node.strandB.light) / 2;
      drawTube(node.strandA, node.strandB, Math.max(2.2, 5 * scale), 118 + light * 120, rungAlpha * .86);
      for (let atom = 1; atom <= 3; atom += 1) {
        const amount = atom / 4;
        drawSphere({
          x: lerp(node.strandA.x, node.strandB.x, amount),
          y: lerp(node.strandA.y, node.strandB.y, amount),
        }, Math.max(1.2, 2.8 * scale), 196, rungAlpha * .72);
      }
    });

    dna.nodes.forEach((node) => {
      if (node.index % 2 !== 0) return;
      drawSphere(node.strandA, Math.max(3, node.strandA.scale * 6), 220 * node.strandA.light, alpha);
      drawSphere(node.strandB, Math.max(3, node.strandB.scale * 6), 220 * node.strandB.light, alpha);
    });
    return dna;
  }

  function buildNetwork(time) {
    const firstLayerReveal = smooth((time - SHIFT_END + .45) / 1.2);
    const reveal = smooth((time - NETWORK_START) / (SCROLL_END_TIME - NETWORK_START - .35));
    const left = width < 760 ? width * .38 : width * .43;
    const right = width < 760 ? width * .93 : width * .9;
    const verticalSpan = Math.min(height * .7, 650);
    const layers = NETWORK_COUNTS.map((count, layerIndex) => {
      const layerAmount = layerIndex / (NETWORK_COUNTS.length - 1);
      const x = lerp(left, right, layerAmount);
      const nodes = Array.from({ length: count }, (_, nodeIndex) => {
        const amount = count === 1 ? .5 : nodeIndex / (count - 1);
        const depth = ((nodeIndex + layerIndex) % 3 - 1) * 34 + Math.sin(nodeIndex * 1.7 + layerIndex) * 12;
        return {
          x: x + depth * .28,
          y: height * .5 + (amount - .5) * verticalSpan - depth * .12,
          depth,
          layerIndex,
          nodeIndex,
        };
      });
      return {
        nodes,
        reveal: layerIndex === 0
          ? firstLayerReveal
          : smooth(reveal * (NETWORK_COUNTS.length + .35) - (layerIndex - 1) * .92),
      };
    });
    return { layers, reveal };
  }

  function drawNetwork(time, network) {
    const { layers, reveal } = network;
    for (let layerIndex = 0; layerIndex < layers.length - 1; layerIndex += 1) {
      const layer = layers[layerIndex];
      const nextLayer = layers[layerIndex + 1];
      const connectionAlpha = Math.min(layer.reveal, nextLayer.reveal);
      if (connectionAlpha <= .003) continue;
      layer.nodes.forEach((from) => nextLayer.nodes.forEach((to) => {
        const selector = (from.nodeIndex * 7 + to.nodeIndex * 11 + layerIndex * 5) % 9;
        if (selector > 4) return;
        const activation = smooth(reveal * (layers.length + .6) - layerIndex - selector * .035);
        line(from, to, connectionAlpha * (.035 + activation * .09), .55 + activation * .35, selector === 0 ? WHITE : "150,150,148");
        if (selector === 0 && activation > .12) {
          const travel = clamp(activation * 1.45 - .22);
          drawSphere({ x: lerp(from.x, to.x, travel), y: lerp(from.y, to.y, travel) }, 2.1, 248, connectionAlpha * activation);
        }
      }));
    }

    layers.forEach((layer, layerIndex) => {
      if (layer.reveal <= .003) return;
      if (layer.nodes.length > 1) line(layer.nodes[0], layer.nodes[layer.nodes.length - 1], layer.reveal * .2, 1, "118,118,116");
      layer.nodes.forEach((node) => {
        const activation = smooth(reveal * (layers.length + .7) - layerIndex - node.nodeIndex * .018);
        drawSphere(node, 3.4 + activation * 2.2, 150 + activation * 98, layer.reveal * (.55 + activation * .45));
      });
    });
  }

  function drawTokenFlow(time, dna, network) {
    const progress = smooth((time - SHIFT_END + .25) / (TOKEN_END - SHIFT_END + .15));
    if (progress <= .003) return;
    const origins = dna.nodes.filter((node) => node.index % 3 === 1);
    const targets = network.layers[0].nodes;
    origins.forEach((originNode, index) => {
      const target = targets[index % targets.length];
      const localProgress = smooth(progress * 1.35 - index * .025);
      if (localProgress <= .003) return;
      const origin = originNode.middle;
      const controlA = { x: origin.x + width * .09, y: origin.y };
      const controlB = { x: target.x - width * .075, y: target.y };
      const position = pointOnCurve(origin, controlA, controlB, target, localProgress);
      const previous = pointOnCurve(origin, controlA, controlB, target, clamp(localProgress - .1));
      line(previous, position, .42 + localProgress * .48, 1.2);

      context.save();
      context.translate(position.x, position.y);
      context.rotate(time * .65 + index * .41);
      const size = 8 + localProgress * 5;
      context.fillStyle = "#060606";
      context.strokeStyle = `rgba(${WHITE},${.7 + localProgress * .3})`;
      context.lineWidth = 1.4;
      context.fillRect(-size / 2, -size / 2, size, size);
      context.strokeRect(-size / 2, -size / 2, size, size);
      context.fillStyle = `rgba(${WHITE},${localProgress})`;
      context.fillRect(-1.6, -1.6, 3.2, 3.2);
      context.restore();
    });
  }

  function render(time) {
    context.clearRect(0, 0, width, height);
    const network = buildNetwork(time);
    const dnaFade = 1 - network.reveal * .58;
    const dna = drawRealisticDna(time, dnaFade);
    drawNetwork(time, network);
    drawTokenFlow(time, dna, network);
  }

  function phaseForTime(time) {
    if (time < 2.35) return 0;
    if (time < SPIN_END) return 1;
    if (time < 7.9) return 2;
    if (time < 10.4) return 3;
    return 4;
  }

  function updateRail(progress, time) {
    const phase = phaseForTime(time);
    railFill.style.height = `${progress * 100}%`;
    railCurrent.textContent = String(phase + 1).padStart(2, "0");
    railStages.forEach((stage, index) => {
      const active = index === phase;
      stage.classList.toggle("is-active", active);
      if (active) stage.setAttribute("aria-current", "step");
      else stage.removeAttribute("aria-current");
    });
  }

  function startRenderLoop() {
    if (frameId === null) frameId = requestAnimationFrame(animate);
  }

  function updateScrollTarget() {
    const availableScroll = Math.max(1, story.offsetHeight - window.innerHeight);
    const progress = isFrozenPreview
      ? clamp((requestedTime - SCROLL_START_TIME) / (SCROLL_END_TIME - SCROLL_START_TIME))
      : clamp(window.scrollY / availableScroll);
    targetElapsed = isFrozenPreview
      ? requestedTime
      : SCROLL_START_TIME + progress * (SCROLL_END_TIME - SCROLL_START_TIME);
    if (prefersReducedMotion || isFrozenPreview) elapsed = targetElapsed;
    story.classList.toggle("has-scrolled", progress > .012);
    updateRail(progress, targetElapsed);
    startRenderLoop();
  }

  railStages.forEach((stage) => stage.addEventListener("click", () => {
    const time = Number(stage.dataset.time);
    const availableScroll = Math.max(1, story.offsetHeight - window.innerHeight);
    window.scrollTo({
      top: clamp((time - SCROLL_START_TIME) / (SCROLL_END_TIME - SCROLL_START_TIME)) * availableScroll,
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }));

  function animate(now) {
    const delta = Math.min((now - lastFrame) / 1000, .05);
    lastFrame = now;
    const distance = targetElapsed - elapsed;
    if (!prefersReducedMotion && !isFrozenPreview) {
      const smoothing = 1 - Math.pow(.0007, delta);
      elapsed += distance * smoothing;
    }
    render(elapsed);
    if (Math.abs(targetElapsed - elapsed) > .0007) frameId = requestAnimationFrame(animate);
    else {
      elapsed = targetElapsed;
      render(elapsed);
      frameId = null;
    }
  }

  window.addEventListener("scroll", updateScrollTarget, { passive: true });
  window.addEventListener("resize", () => {
    resize();
    updateScrollTarget();
  });
  resize();
  updateScrollTarget();
})();
