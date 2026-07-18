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
  const ORBIT_END = 5.25;
  const TOKEN_END = 8.25;
  const VECTOR_END = 12.1;
  const WHITE = "248,248,246";
  const SOFT_WHITE = "204,204,200";
  const FOCAL = 920;
  const DNA_SEGMENTS = 46;
  const requestedTime = Number(new URLSearchParams(window.location.search).get("t"));
  const isFrozenPreview = Number.isFinite(requestedTime) && window.location.search.includes("t=");

  let width = 0;
  let height = 0;
  let dpr = 1;
  let elapsed = isFrozenPreview ? modPreview(requestedTime) : SCROLL_START_TIME;
  let targetElapsed = elapsed;
  let lastFrame = performance.now();

  const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
  const mod = (value, divisor) => ((value % divisor) + divisor) % divisor;
  const lerp = (from, to, amount) => from + (to - from) * amount;
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };

  function modPreview(value) {
    return ((value % LOOP_DURATION) + LOOP_DURATION) % LOOP_DURATION;
  }

  function resize() {
    const bounds = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = bounds.width;
    height = bounds.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function point(x, y, z, centerX = width * .5, centerY = height * .5) {
    const scale = FOCAL / (FOCAL + z);
    return { x: centerX + x * scale, y: centerY + y * scale, scale, z };
  }

  function alphaForDepth(z, strength = 1) {
    return clamp((z + 120) / 470) * clamp((2240 - z) / 540) * strength;
  }

  function line(from, to, alpha, lineWidth = 1, color = WHITE) {
    if (alpha <= .004) return;
    context.save();
    context.strokeStyle = `rgba(${color}, ${alpha})`;
    context.lineWidth = lineWidth;
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.restore();
  }

  function dot(position, radius, alpha, color = WHITE) {
    if (alpha <= .004) return;
    context.save();
    context.fillStyle = `rgba(${color}, ${alpha})`;
    context.beginPath();
    context.arc(position.x, position.y, radius, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function token(position, size, angle, alpha) {
    if (alpha <= .004) return;
    context.save();
    context.translate(position.x, position.y);
    context.rotate(angle);
    context.fillStyle = `rgba(0,0,0,${alpha * .85})`;
    context.strokeStyle = `rgba(${WHITE},${alpha})`;
    context.lineWidth = Math.max(.8, size * .08);
    context.fillRect(-size / 2, -size / 2, size, size);
    context.strokeRect(-size / 2, -size / 2, size, size);
    context.fillStyle = `rgba(${WHITE},${alpha})`;
    context.fillRect(-size * .13, -size * .13, size * .26, size * .26);
    context.restore();
  }

  function projectHelixPoint(x, y, z, camera) {
    const cosYaw = Math.cos(camera.yaw);
    const sinYaw = Math.sin(camera.yaw);
    const cosPitch = Math.cos(camera.pitch);
    const sinPitch = Math.sin(camera.pitch);
    const cosRoll = Math.cos(camera.roll);
    const sinRoll = Math.sin(camera.roll);
    const yawX = x * cosYaw + z * sinYaw;
    const yawZ = -x * sinYaw + z * cosYaw;
    const pitchY = y * cosPitch - yawZ * sinPitch;
    const depth = camera.distance + y * sinPitch + yawZ * cosPitch;
    const rolledX = yawX * cosRoll - pitchY * sinRoll;
    const rolledY = yawX * sinRoll + pitchY * cosRoll;
    const scale = FOCAL / (FOCAL + depth);
    return {
      x: camera.centerX + rolledX * scale,
      y: camera.centerY + rolledY * scale,
      z: depth,
      scale,
    };
  }

  function helixCamera(time) {
    const progress = smooth(time / ORBIT_END);
    return {
      centerX: width * .5,
      centerY: height * .5,
      yaw: -.72 + progress * Math.PI * 1.8,
      pitch: .14 - Math.sin(progress * Math.PI) * .34,
      roll: lerp(-.61, -.24, progress),
      distance: lerp(970, 245, progress),
    };
  }

  function getHelix(time) {
    const camera = helixCamera(Math.min(time, ORBIT_END));
    const radius = Math.min(width, height) * .115;
    const rise = Math.min(width, height) * .052;
    const nodes = [];

    for (let index = 0; index < DNA_SEGMENTS; index += 1) {
      const theta = index * .54 + time * .22;
      const y = (index - (DNA_SEGMENTS - 1) / 2) * rise;
      const pulse = Math.sin(index * .63 + time * 3.4) * 2.5;
      const strandA = projectHelixPoint(Math.cos(theta) * (radius + pulse), y, Math.sin(theta) * (radius + pulse), camera);
      const strandB = projectHelixPoint(Math.cos(theta + Math.PI) * (radius + pulse), y, Math.sin(theta + Math.PI) * (radius + pulse), camera);
      nodes.push({ strandA, strandB, index });
    }
    return nodes;
  }

  function drawExteriorDna(time, alpha) {
    if (alpha <= .004) return [];
    const helix = getHelix(time);
    const renderOrder = [...helix].sort((a, b) => b.strandA.z - a.strandA.z);

    for (let index = 0; index < helix.length - 1; index += 1) {
      const current = helix[index];
      const next = helix[index + 1];
      line(current.strandA, next.strandA, alpha * .92, Math.max(1.1, current.strandA.scale * 2.3), SOFT_WHITE);
      line(current.strandB, next.strandB, alpha * .92, Math.max(1.1, current.strandB.scale * 2.3), SOFT_WHITE);
    }

    renderOrder.forEach((segment) => {
      const rungAlpha = alpha * (.58 + Math.sin(time * 2.8 + segment.index) * .1);
      line(segment.strandA, segment.strandB, rungAlpha, Math.max(1.2, segment.strandA.scale * 3.1));
      if (segment.index % 2 === 0) {
        dot(segment.strandA, Math.max(1.1, segment.strandA.scale * 2.6), alpha * .95);
        dot(segment.strandB, Math.max(1.1, segment.strandB.scale * 2.6), alpha * .95);
      }
    });
    return helix;
  }

  function vectorTokenPosition(index, time) {
    const theta = index * 2.399 + time * 1.33;
    const altitude = Math.sin(index * 1.72 + time * 1.6);
    const radius = 58 + (index % 9) * 19 + Math.sin(time * 3 + index) * 7;
    const z = 190 + mod(index * 137 - (time - TOKEN_END) * 155, 1080);
    return point(Math.cos(theta) * radius * 2.5, altitude * radius * 2.15, z);
  }

  function drawTokenization(time, alpha, helix) {
    if (alpha <= .004) return;
    const progress = smooth((time - ORBIT_END + .2) / (TOKEN_END - ORBIT_END + .2));
    helix.forEach((segment, index) => {
      const origin = {
        x: (segment.strandA.x + segment.strandB.x) / 2,
        y: (segment.strandA.y + segment.strandB.y) / 2,
      };
      const target = vectorTokenPosition(index, time);
      const position = {
        x: lerp(origin.x, target.x, progress),
        y: lerp(origin.y, target.y, progress),
      };
      const flicker = .7 + Math.sin(time * 10 + index * 1.7) * .3;
      const size = lerp(3.5, clamp(11 + target.scale * 16, 9, 25), progress);
      line(origin, position, alpha * progress * .3 * flicker, Math.max(.4, size * .06));
      for (let trail = 1; trail <= 3; trail += 1) {
        const trailProgress = clamp(progress - trail * .045);
        const trailPosition = {
          x: lerp(origin.x, target.x, trailProgress),
          y: lerp(origin.y, target.y, trailProgress),
        };
        token(trailPosition, size * (1 - trail * .15), time * .9 + index * .43, alpha * .12 * (4 - trail));
      }
      token(position, size, time * .9 + index * .43, alpha * (.4 + progress * .6) * flicker);
    });

    const burst = clamp((progress - .12) / .55);
    for (let ring = 0; ring < 3; ring += 1) {
      const radius = (burst * 330 + ring * 72) % 360;
      context.save();
      context.strokeStyle = `rgba(${WHITE},${alpha * .13 * (1 - radius / 360)})`;
      context.lineWidth = 1;
      context.beginPath();
      context.arc(width * .5, height * .5, radius, 0, Math.PI * 2);
      context.stroke();
      context.restore();
    }
  }

  function drawVectorSpace(time, alpha) {
    if (alpha <= .004) return;
    const localTime = time - TOKEN_END;
    const center = { x: width * .5, y: height * .5 };
    const particleCount = 180;
    const particles = [];

    for (let index = 0; index < particleCount; index += 1) {
      const orbit = index * 2.399 + localTime * (1.1 + (index % 5) * .08);
      const fieldRadius = 38 + (index % 18) * 18;
      const z = 120 + mod(index * 103 - localTime * (245 + (index % 7) * 12), 1420);
      const x = Math.cos(orbit) * fieldRadius * (1.1 + Math.sin(localTime * 1.2 + index) * .25);
      const y = Math.sin(orbit * 1.19) * fieldRadius * .7 + Math.cos(localTime * 2 + index) * 14;
      const projected = point(x, y, z);
      particles.push({ ...projected, index, orbit, z, worldX: x, worldY: y });
    }

    particles.sort((a, b) => b.z - a.z);
    particles.forEach((particle, index) => {
      const next = particles[(index + 17) % particles.length];
      const connectionPulse = (Math.sin(localTime * 9 + particle.index * .73) + 1) * .5;
      if (particle.index % 3 === 0) {
        line(particle, next, alphaForDepth(particle.z, alpha * (.035 + connectionPulse * .13)), Math.max(.35, particle.scale * .3));
      }
      const depthTrail = point(particle.worldX, particle.worldY, particle.z + 95 + (particle.index % 5) * 24);
      line(depthTrail, particle, alphaForDepth(particle.z, alpha * (.06 + connectionPulse * .2)), Math.max(.35, particle.scale * .45));
      const radius = clamp(particle.scale * (1.1 + connectionPulse * 1.7), .4, 4.8);
      dot(particle, radius, alphaForDepth(particle.z, alpha * (.25 + connectionPulse * .67)));
    });

    for (let ring = 0; ring < 5; ring += 1) {
      const radius = mod(localTime * (95 + ring * 13) + ring * 177, Math.min(width, height) * .58);
      context.save();
      context.strokeStyle = `rgba(${WHITE}, ${alpha * .1 * (1 - radius / (Math.min(width, height) * .58))})`;
      context.lineWidth = 1;
      context.beginPath();
      context.ellipse(center.x, center.y, radius, radius * .56, localTime * .38 + ring, 0, Math.PI * 2);
      context.stroke();
      context.restore();
    }

    for (let index = 0; index < DNA_SEGMENTS; index += 1) {
      const position = vectorTokenPosition(index, time);
      const size = clamp(8 + position.scale * 16, 8, 23);
      token(position, size, localTime * 1.4 + index * .55, alpha * (.58 + Math.sin(localTime * 6 + index) * .25));
    }
  }

  function neuralPosition(layer, node, time) {
    const row = Math.floor(node / 3) - 1;
    const column = node % 3 - 1;
    const spread = 115 + (layer % 3) * 20;
    return {
      x: column * spread + Math.sin(time * .8 + layer + node) * 18,
      y: row * spread * .78 + Math.cos(time * .7 + layer * .9 + node) * 16,
    };
  }

  function drawNeuralNetwork(time, alpha) {
    if (alpha <= .004) return;
    const localTime = time - VECTOR_END;
    const layers = [];
    const layerCount = 11;
    const nodeCount = 9;

    for (let layer = 0; layer < layerCount; layer += 1) {
      const z = 85 + mod(layer * 250 - localTime * 385, 2100);
      const nodes = [];
      for (let node = 0; node < nodeCount; node += 1) {
        const position = neuralPosition(layer, node, time);
        nodes.push({ ...point(position.x, position.y, z), z, layer, node });
      }
      layers.push({ z, nodes });
    }

    layers.sort((a, b) => b.z - a.z);
    for (let layer = 0; layer < layers.length - 1; layer += 1) {
      layers[layer].nodes.forEach((from) => {
        [from.node, (from.node + 1) % nodeCount, (from.node + 3) % nodeCount].forEach((target) => {
          const to = layers[layer + 1].nodes[target];
          const pulse = (Math.sin(localTime * 8.5 - from.layer * .9 - from.node * .55) + 1) * .5;
          line(from, to, alphaForDepth(from.z, alpha * (.055 + pulse * .25)), Math.max(.4, from.scale * .48));
        });
      });
    }

    layers.forEach((layer) => layer.nodes.forEach((node) => {
      const pulse = (Math.sin(localTime * 8.5 - node.layer * .9 - node.node * .55) + 1) * .5;
      dot(node, clamp(node.scale * (1.5 + pulse * 1.65), .7, 5.4), alphaForDepth(node.z, alpha * (.35 + pulse * .65)));
    }));
  }

  function render(time) {
    context.clearRect(0, 0, width, height);
    const loopFade = Math.min(smooth(time / .62), 1 - smooth((time - 14.35) / .65));
    const tokenProgress = smooth((time - ORBIT_END + .18) / (TOKEN_END - ORBIT_END + .18));
    const vectorProgress = smooth((time - TOKEN_END + .45) / .95);
    const networkProgress = smooth((time - VECTOR_END + .55) / 1.15);
    const helix = drawExteriorDna(time, (1 - tokenProgress) * loopFade);
    drawTokenization(time, tokenProgress * loopFade, helix);
    drawVectorSpace(time, vectorProgress * (1 - networkProgress) * loopFade);
    drawNeuralNetwork(time, networkProgress * loopFade);
  }

  function phaseForTime(time) {
    if (time < 2.45) return 0;
    if (time < ORBIT_END) return 1;
    if (time < TOKEN_END) return 2;
    if (time < VECTOR_END) return 3;
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
    if (!prefersReducedMotion && !isFrozenPreview) {
      const smoothing = 1 - Math.pow(.0007, delta);
      elapsed += (targetElapsed - elapsed) * smoothing;
    }
    render(elapsed);
    requestAnimationFrame(animate);
  }

  window.addEventListener("scroll", updateScrollTarget, { passive: true });
  window.addEventListener("resize", () => {
    resize();
    updateScrollTarget();
  });
  resize();
  updateScrollTarget();
  requestAnimationFrame(animate);
})();
