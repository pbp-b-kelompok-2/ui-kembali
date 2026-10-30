(() => {
  const carousel = document.querySelector('.lobby-tag-carousel');
  const track = carousel?.querySelector('.lobby-hanging-tags');
  if (!carousel || !track) return;

  const originalTags = Array.from(track.children);
  originalTags.forEach((tag) => {
    const clone = tag.cloneNode(true);
    clone.setAttribute('aria-hidden', 'true');
    track.appendChild(clone);
  });

  const loopPoint = track.children[originalTags.length].offsetLeft - track.children[0].offsetLeft;
  const swingStates = new Map();
  let activeTag = null;
  let isDraggingTrack = false;
  let pointerStartX = 0;
  let pointerStartY = 0;
  let scrollStart = 0;
  let lastPointerAngle = 0;
  let lastPointerAt = 0;
  let lastTickAt = performance.now();

  const getTagPivot = (tag) => {
    const carouselRect = carousel.getBoundingClientRect();
    const pivotOffsetY = Number.parseFloat(getComputedStyle(tag).transformOrigin.split(' ')[1]) || 0;
    return {
      x: carouselRect.left + track.offsetLeft + tag.offsetLeft - carousel.scrollLeft + tag.offsetWidth / 2,
      y: carouselRect.top + track.offsetTop + tag.offsetTop - carousel.scrollTop + pivotOffsetY,
    };
  };

  carousel.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
    carousel.classList.add('is-dragging');
    carousel.setPointerCapture(event.pointerId);

    const tag = event.target instanceof Element ? event.target.closest('.lobby-tag') : null;
    if (tag) {
      event.preventDefault();
      activeTag = tag;
      activeTag.classList.add('is-picked-up');
      carousel.classList.add('is-picking-tag');
      const angle = Number.parseFloat(activeTag.dataset.swingAngle || '0');
      swingStates.set(activeTag, { angle, velocity: 0 });
      const pivot = getTagPivot(activeTag);
      lastPointerAngle = Math.atan2(event.clientY - pivot.y, event.clientX - pivot.x) * 180 / Math.PI;
      lastPointerAt = performance.now();
    } else {
      isDraggingTrack = true;
      scrollStart = carousel.scrollLeft;
    }
  });

  carousel.addEventListener('pointermove', (event) => {
    if (activeTag) {
      const now = performance.now();
      const elapsed = Math.max((now - lastPointerAt) / 1000, 0.001);
      const state = swingStates.get(activeTag);
      const pivot = getTagPivot(activeTag);
      const pointerAngle = Math.atan2(event.clientY - pivot.y, event.clientX - pivot.x) * 180 / Math.PI;
      const pointerDelta = ((pointerAngle - lastPointerAngle + 540) % 360) - 180;
      const angle = state.angle + pointerDelta;
      state.velocity = Math.max(-180, Math.min(180, (angle - state.angle) / elapsed));
      state.angle = angle;
      lastPointerAngle = pointerAngle;
      activeTag.dataset.swingAngle = String(angle);
      activeTag.style.setProperty('--swing-angle', `${angle}deg`);
      lastPointerAt = now;
    } else if (isDraggingTrack) {
      carousel.scrollLeft = scrollStart - (event.clientX - pointerStartX);
    }
  });

  const finishDrag = () => {
    if (activeTag) {
      const state = swingStates.get(activeTag);
      if (state) {
        // Resolve equivalent turns to the shortest angle back to rest. This
        // prevents a tag released past 180 degrees from unwinding the long way.
        state.angle = ((state.angle + 540) % 360) - 180;
        state.velocity = 0;
        activeTag.dataset.swingAngle = String(state.angle);
        activeTag.style.setProperty('--swing-angle', `${state.angle}deg`);
      }
      activeTag.classList.remove('is-picked-up');
      activeTag = null;
      carousel.classList.remove('is-picking-tag');
    }
    isDraggingTrack = false;
    carousel.classList.remove('is-dragging');
  };
  carousel.addEventListener('pointerup', finishDrag);
  carousel.addEventListener('pointercancel', finishDrag);
  carousel.addEventListener('lostpointercapture', finishDrag);

  window.setInterval(() => {
    const now = performance.now();
    const elapsed = Math.min((now - lastTickAt) / 1000, 0.04);
    lastTickAt = now;

    if (!activeTag && !isDraggingTrack && loopPoint > 0) {
      carousel.scrollLeft += elapsed * 72;
      if (carousel.scrollLeft >= loopPoint) carousel.scrollLeft -= loopPoint;
    }

    swingStates.forEach((state, tag) => {
      if (tag === activeTag) return;
      const acceleration = -state.angle * 14 - state.velocity * 7;
      state.velocity += acceleration * elapsed;
      state.angle += state.velocity * elapsed;
      if (Math.abs(state.angle) < 0.08 && Math.abs(state.velocity) < 0.3) {
        tag.style.setProperty('--swing-angle', '0deg');
        tag.dataset.swingAngle = '0';
        swingStates.delete(tag);
      } else {
        tag.style.setProperty('--swing-angle', `${state.angle}deg`);
        tag.dataset.swingAngle = String(state.angle);
      }
    });
  }, 16);
})();
