(() => {
  const canvas = document.getElementById("sequence-canvas");
  const context = canvas.getContext("2d");
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const LOOP_DURATION = 15;
  const SEQUENCE_START = .75;
  const SEQUENCE_END = 14.2;
  const SPIN_END = 5.1;
  const SHIFT_END = 7;
  const TOKEN_END = 9.35;
  const NETWORK_START = 9.15;
  const WHITE = "248,248,246";
  const DNA_SEGMENTS = 39;
  const NETWORK_COUNTS = [30, 26, 22, 18, 14, 10, 7, 4, 1];
  const requestedTime = Number(new URLSearchParams(window.location.search).get("t"));
  const isFrozenPreview = Number.isFinite(requestedTime) && window.location.search.includes("t=");

  let width = 0;
  let height = 0;
  let dpr = 1;
  let elapsed = isFrozenPreview ? normalizeTime(requestedTime) : prefersReducedMotion ? 12.2 : 0;
  let lastFrame = performance.now();
  let lastRender = lastFrame;
  const pointer = { x: -9999, y: -9999 };

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
    const spin = smooth((time - SEQUENCE_START) / (SPIN_END - SEQUENCE_START));
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
    const firstLayerReveal = smooth((time - SHIFT_END + .2) / 1.4);
    const reveal = smooth((time - NETWORK_START) / (SEQUENCE_END - NETWORK_START - .35));
    const focus = smooth((time - 9.25) / 1.45);
    const stagedLeft = width < 760 ? width * .43 : width * .45;
    const stagedRight = width < 760 ? width * .91 : width * .88;
    const left = lerp(stagedLeft, width * .07, focus);
    const right = lerp(stagedRight, width * .93, focus);
    const verticalSpan = lerp(
      Math.min(height * .78, 760),
      Math.min(height * .86, 860),
      focus,
    );
    const layers = NETWORK_COUNTS.map((count, layerIndex) => {
      const layerAmount = layerIndex / (NETWORK_COUNTS.length - 1);
      const x = lerp(left, right, layerAmount);
      const nodes = Array.from({ length: count }, (_, nodeIndex) => {
        const amount = count === 1 ? .5 : nodeIndex / (count - 1);
        const depth = ((nodeIndex + layerIndex) % 3 - 1) * 16 + Math.sin(nodeIndex * 1.7 + layerIndex) * 5;
        return {
          x: x + depth * .2,
          y: height * .5 + (amount - .5) * verticalSpan - depth * .08,
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

  function hoverActivation(node) {
    return clamp(1 - Math.hypot(node.x - pointer.x, node.y - pointer.y) / 185);
  }

  function drawSynapseNode(node, radius, alpha, activation) {
    if (alpha <= .003) return;
    context.save();
    context.shadowColor = `rgba(${WHITE},${.36 + activation * .58})`;
    context.shadowBlur = 7 + activation * 13;
    context.fillStyle = `rgba(${WHITE},${alpha * (.72 + activation * .28)})`;
    context.beginPath();
    context.arc(node.x, node.y, radius + activation * 1.8, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function drawNetwork(time, network) {
    const { layers, reveal } = network;

    for (let layerIndex = 0; layerIndex < layers.length - 1; layerIndex += 1) {
      const layer = layers[layerIndex];
      const nextLayer = layers[layerIndex + 1];
      const connectionAlpha = Math.min(layer.reveal, nextLayer.reveal);
      if (connectionAlpha <= .003) continue;
      layer.nodes.forEach((from) => nextLayer.nodes.forEach((to) => {
        const selector = (from.nodeIndex * 7 + to.nodeIndex * 11 + layerIndex * 5) % 13;
        if (selector > 5) return;
        const hover = Math.max(hoverActivation(from), hoverActivation(to));
        const baseActivation = smooth(reveal * (layers.length + .7) - layerIndex - selector * .032);
        const activation = Math.max(baseActivation, hover);
        line(from, to, connectionAlpha * (.045 + activation * .135), .52 + activation * .48, activation > .76 ? WHITE : "124,124,122");
        if (selector === 0 && activation > .1) {
          const travel = mod(time * .34 + layerIndex * .17 + selector * .29 + from.nodeIndex * .07, 1);
          const pulse = { x: lerp(from.x, to.x, travel), y: lerp(from.y, to.y, travel) };
          const tail = { x: lerp(from.x, to.x, clamp(travel - .055)), y: lerp(from.y, to.y, clamp(travel - .055)) };
          line(tail, pulse, connectionAlpha * activation * .72, 1.3, WHITE);
          drawSynapseNode(pulse, 1.7, connectionAlpha * activation, activation);
        }
      }));
    }

    layers.forEach((layer, layerIndex) => {
      if (layer.reveal <= .003) return;
      layer.nodes.forEach((node) => {
        const baseActivation = smooth(reveal * (layers.length + .7) - layerIndex - node.nodeIndex * .018);
        const activation = Math.max(baseActivation, hoverActivation(node));
        drawSynapseNode(node, 2.35 + activation * 1.4, layer.reveal, activation);
      });
    });
  }

  function drawParticleFlow(time, dna, network) {
    const progress = smooth((time - SHIFT_END + .25) / (TOKEN_END - SHIFT_END + .15));
    if (progress <= .003) return;
    const sources = dna.nodes.filter((node) => node.index % 2 === 0);
    const targets = network.layers[0].nodes;
    sources.forEach((source, sourceIndex) => {
      for (let fragment = 0; fragment < 4; fragment += 1) {
        const target = targets[(sourceIndex * 7 + fragment * 11) % targets.length];
        const localProgress = smooth(progress * 1.48 - sourceIndex * .015 - fragment * .06);
        if (localProgress <= .003) continue;
        const origin = fragment % 3 === 0
          ? source.strandA
          : fragment % 3 === 1
            ? source.middle
            : source.strandB;
        const phase = sourceIndex * .83 + fragment * 1.7;
        const controlA = {
          x: origin.x + width * (.075 + fragment * .008),
          y: origin.y + Math.sin(phase) * 34,
        };
        const controlB = {
          x: target.x - width * .07,
          y: target.y + Math.cos(phase) * 24,
        };
        const position = pointOnCurve(origin, controlA, controlB, target, localProgress);
        const previous = pointOnCurve(origin, controlA, controlB, target, clamp(localProgress - .055));
        const arrivalFade = 1 - smooth((localProgress - .9) / .1) * .62;
        line(previous, position, arrivalFade * (.26 + localProgress * .5), .7 + fragment * .08);
        drawSynapseNode(position, 1.15 + fragment * .16, arrivalFade, .42 + localProgress * .58);
      }
    });
  }

  function render(time) {
    context.clearRect(0, 0, width, height);
    const sceneAlpha = Math.min(
      smooth(time / .6),
      1 - smooth((time - SEQUENCE_END) / (LOOP_DURATION - SEQUENCE_END)),
    );
    context.save();
    context.globalAlpha = sceneAlpha;
    const network = buildNetwork(time);
    const dnaFade = 1 - smooth((time - 8.05) / 1.05);
    const dna = drawRealisticDna(time, dnaFade);
    drawNetwork(time, network);
    drawParticleFlow(time, dna, network);
    context.restore();
  }

  function animate(now) {
    if (now - lastRender < 1000 / 30) {
      requestAnimationFrame(animate);
      return;
    }
    const delta = Math.min((now - lastFrame) / 1000, .08);
    lastFrame = now;
    lastRender = now;
    if (!prefersReducedMotion && !isFrozenPreview) {
      elapsed = mod(elapsed + delta, LOOP_DURATION);
    }
    render(elapsed);
    if (!prefersReducedMotion && !isFrozenPreview) requestAnimationFrame(animate);
  }

  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    if (prefersReducedMotion || isFrozenPreview) render(elapsed);
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => {
    pointer.x = -9999;
    pointer.y = -9999;
    if (prefersReducedMotion || isFrozenPreview) render(elapsed);
  });
  window.addEventListener("resize", () => {
    resize();
    render(elapsed);
  });
  resize();
  render(elapsed);
  if (!prefersReducedMotion && !isFrozenPreview) requestAnimationFrame(animate);
})();
