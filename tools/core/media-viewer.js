(() => {
  "use strict";
  const protectedImage = (target) => target instanceof Element &&
    Boolean(target.closest("img.media-protected-image, img[data-viewer-image]"));
  document.addEventListener("contextmenu", (event) => {
    if (protectedImage(event.target)) event.preventDefault();
  });
  document.addEventListener("dragstart", (event) => {
    if (protectedImage(event.target)) event.preventDefault();
  });
  const dialog = document.querySelector("dialog.media-viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const image = dialog.querySelector("[data-viewer-image]");
  const spread = dialog.querySelector("[data-viewer-spread]");
  const leftPage = dialog.querySelector("[data-viewer-left]");
  const rightPage = dialog.querySelector("[data-viewer-right]");
  const leftSlot = dialog.querySelector("[data-viewer-slot-left]");
  const rightSlot = dialog.querySelector("[data-viewer-slot-right]");
  const caption = dialog.querySelector("[data-viewer-caption]");
  const position = dialog.querySelector("[data-viewer-position]");
  const stage = dialog.querySelector("[data-viewer-stage]");
  const controls = Object.fromEntries([...dialog.querySelectorAll("[data-viewer-action]")]
    .map((button) => [button.dataset.viewerAction, button]));
  const modeButtons = [...dialog.querySelectorAll("[data-viewer-mode]")];
  const sideButtons = [...dialog.querySelectorAll("[data-viewer-side]")];
  let active = null;
  let mode = "single";
  let firstSide = "right";
  let previousFocus = null;
  let previousOverflow = null;
  let previousBodyOverflow = null;
  let scale = 1;
  let fitScale = 1;
  let scaleAdjusted = false;
  let touchStart = null;
  let dragStart = null;
  const visibleImages = () => mode === "manga"
    ? [leftPage, rightPage].filter((node) => !node.hidden && node.naturalWidth)
    : (image.naturalWidth ? [image] : []);
  const pages = () => [...document.querySelectorAll("a.media-viewer-trigger")];
  const spreadPlan = (count) => {
    const frames = [];
    const leading = dialog.dataset.readingDirection === "rtl" ? "right" : "left";
    const trailing = leading === "right" ? "left" : "right";
    let page = 0;
    if (count && firstSide !== leading) {
      const frame = {right: null, left: null}; frame[firstSide] = 0;
      frames.push(frame); page = 1;
    }
    while (page < count) {
      const frame = {right: null, left: null}; frame[leading] = page++;
      if (page < count) frame[trailing] = page++;
      frames.push(frame);
    }
    return frames;
  };
  const setPageSource = (node, link) => {
    if (!link) { node.removeAttribute("src"); node.alt = ""; node.hidden = true; return; }
    node.hidden = false;
    if (node.src !== link.href) { node.style.removeProperty("width"); node.style.removeProperty("height"); node.src = link.href; }
    node.alt = link.querySelector("img")?.alt || "";
  };
  const setMode = (nextMode) => {
    mode = nextMode;
    const manga = mode === "manga";
    dialog.classList.toggle("is-manga-mode", manga);
    image.hidden = manga;
    spread.hidden = !manga;
    if (manga) {
      image.removeAttribute("src");
    } else {
      setPageSource(leftPage, null);
      setPageSource(rightPage, null);
    }
    modeButtons.forEach((button) => { button.hidden = !dialog.dataset.viewerModes.split(",").includes(button.dataset.viewerMode); button.setAttribute("aria-pressed", String(button.dataset.viewerMode === mode)); });
    sideButtons.forEach((button) => { button.hidden = !manga || !dialog.dataset.viewerSideOptions.split(",").includes(button.dataset.viewerSide); button.setAttribute("aria-pressed", String(button.dataset.viewerSide === firstSide)); });
  };
  const renderManga = () => {
    const all = pages();
    const index = Number(active?.dataset.viewerIndex || 0);
    const frames = spreadPlan(all.length);
    const frameIndex = frames.findIndex((frame) => frame.right === index || frame.left === index);
    const frame = frames[Math.max(0, frameIndex)] || {right: null, left: null};
    setPageSource(leftPage, frame.left === null ? null : all[frame.left]);
    setPageSource(rightPage, frame.right === null ? null : all[frame.right]);
    const shown = [frame.right, frame.left].filter((value) => value !== null);
    const low = Math.min(...shown) + 1;
    const high = Math.max(...shown) + 1;
    const locale = document.documentElement.lang;
    position.textContent = (locale === "jp" || locale === "ja")
      ? (low === high ? `${low} / ${all.length}ページ` : `${low}–${high} / ${all.length}ページ`)
      : locale === "de"
        ? (low === high ? `${low} / ${all.length}` : `Seiten ${low}–${high} / ${all.length}`)
        : (low === high ? `${low} / ${all.length}` : `Pages ${low}–${high} / ${all.length}`);
    controls.previous.disabled = frameIndex <= 0;
    controls.next.disabled = frameIndex < 0 || frameIndex >= frames.length - 1;
    caption.textContent = [frame.right, frame.left].filter((value) => value !== null).map((n) => all[n].dataset.viewerCaption || "").filter(Boolean).join(" · ");
    stage.classList.remove("is-zoomed");
    stage.scrollTo(0, 0);
  };
  const measureFit = () => {
    if (mode === "manga") {
      const shown = visibleImages();
      if (!shown.length) return false;
      const width = shown.reduce((sum, node) => sum + node.naturalWidth, 0) * (shown.length === 1 ? 2 : 1);
      const height = Math.max(...shown.map((node) => node.naturalHeight));
      fitScale = Math.min(stage.clientWidth / width, stage.clientHeight / height);
      return Number.isFinite(fitScale) && fitScale > 0;
    }
    if (!image.naturalWidth || !image.naturalHeight) return false;
    fitScale = Math.min(stage.clientWidth / image.naturalWidth, stage.clientHeight / image.naturalHeight);
    if (!Number.isFinite(fitScale) || fitScale <= 0) return false;
    return true;
  };
  const renderScale = () => {
    if (mode === "manga") {
      const shown = visibleImages();
      if (!shown.length) return;
      let width = 0; let height = 0;
      shown.forEach((node) => {
        const nodeWidth = node.naturalWidth * scale; const nodeHeight = node.naturalHeight * scale;
        node.style.width = `${nodeWidth}px`; node.style.height = `${nodeHeight}px`;
        width += nodeWidth; height = Math.max(height, nodeHeight);
      });
      const blankWidth = shown.length === 1 ? shown[0].naturalWidth * scale : 0;
      leftSlot.style.width = `${leftPage.hidden ? blankWidth : leftPage.naturalWidth * scale}px`;
      rightSlot.style.width = `${rightPage.hidden ? blankWidth : rightPage.naturalWidth * scale}px`;
      leftSlot.style.height = `${height}px`; rightSlot.style.height = `${height}px`;
      width = leftSlot.offsetWidth + rightSlot.offsetWidth;
      stage.classList.toggle("is-zoomed", width > stage.clientWidth + 1 || height > stage.clientHeight + 1);
      return;
    }
    if (!fitScale || !image.naturalWidth || !image.naturalHeight) return;
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    image.style.width = `${width}px`;
    image.style.height = `${height}px`;
    stage.classList.toggle("is-zoomed", width > stage.clientWidth + 1 || height > stage.clientHeight + 1);
  };
  const fit = () => {
    if (!measureFit()) return;
    scale = fitScale;
    scaleAdjusted = false;
    renderScale();
    stage.scrollTo(0, 0);
  };
  const open = (link) => {
    if (!link || !link.matches("a.media-viewer-trigger")) return;
    const wasClosed = !dialog.open;
    active = link;
    scaleAdjusted = false;
    if (wasClosed) previousFocus = document.activeElement;
    if (wasClosed) {
      previousOverflow = document.documentElement.style.overflow;
      previousBodyOverflow = document.body.style.overflow;
      document.documentElement.style.overflow = "hidden";
      document.body.style.overflow = "hidden";
    }
    if (wasClosed) {
      firstSide = dialog.dataset.viewerFirstSide || "right";
      const preferredMode = window.matchMedia("(max-width: 600px)").matches
        ? dialog.dataset.viewerMobileDefaultMode
        : dialog.dataset.viewerDefaultMode;
      setMode(preferredMode || "single");
    }
    if (mode === "manga") renderManga();
    else {
      image.src = link.href;
      image.alt = link.querySelector("img")?.alt || "";
      caption.textContent = link.dataset.viewerCaption || "";
      position.textContent = link.dataset.viewerPosition || "";
      controls.previous.disabled = !link.dataset.viewerPrevious;
      controls.next.disabled = !link.dataset.viewerNext;
      spread.hidden = true;
      image.hidden = false;
    }
    if (wasClosed) dialog.showModal();
    fit();
    if (wasClosed) controls.close.focus();
  };
  const close = () => { if (dialog.open) dialog.close(); };
  const navigate = (direction) => {
    if (!active) return;
    if (mode === "manga") {
      const all = pages(); const index = Number(active.dataset.viewerIndex || 0); const frames = spreadPlan(all.length);
      const frameIndex = frames.findIndex((frame) => frame.right === index || frame.left === index);
      const targetFrame = frames[frameIndex + (direction === "next" ? 1 : -1)];
      if (!targetFrame) return;
      const targetIndex = targetFrame.right ?? targetFrame.left;
      active = all[targetIndex]; scaleAdjusted = false; renderManga(); fit(); return;
    }
    const target = active.dataset[`viewer${direction === "previous" ? "Previous" : "Next"}`];
    if (!target) return;
    const url = new URL(target, location.href);
    if (url.pathname === location.pathname) {
      const link = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (link) open(link);
      return;
    }
    location.href = url.href;
  };
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a.media-viewer-trigger");
    if (!link) return;
    event.preventDefault();
    open(link);
  });
  const reopenButton = document.querySelector("[data-viewer-reopen]");
  reopenButton?.addEventListener("click", () => open(pages()[0]));
  if (dialog.dataset.viewerOpenOnLoad === "true") {
    const firstPage = pages()[0];
    if (firstPage) open(firstPage);
  }
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  dialog.addEventListener("close", () => {
    image.removeAttribute("src");
    stage.classList.remove("is-zoomed");
    if (previousFocus?.isConnected) previousFocus.focus();
    document.documentElement.style.overflow = previousOverflow ?? "";
    document.body.style.overflow = previousBodyOverflow ?? "";
    previousOverflow = null; previousBodyOverflow = null;
    active = null;
  });
  controls.close.addEventListener("click", close);
  controls.previous.addEventListener("click", () => navigate("previous"));
  controls.next.addEventListener("click", () => navigate("next"));
  modeButtons.forEach((button) => button.addEventListener("click", () => {
    if (!active) return;
    setMode(button.dataset.viewerMode);
    if (mode === "manga") renderManga(); else open(active);
    fit();
  }));
  sideButtons.forEach((button) => button.addEventListener("click", () => {
    firstSide = button.dataset.viewerSide;
    if (mode === "manga") { scaleAdjusted = false; setMode(mode); renderManga(); fit(); }
  }));
  controls.fit.addEventListener("click", fit);
  controls.actual.addEventListener("click", () => {
    if (mode === "manga") {
      if (!visibleImages().length) return;
      measureFit(); scale = 1; scaleAdjusted = true; renderScale(); return;
    }
    if (!image.naturalWidth || !image.naturalHeight) return;
    measureFit();
    scale = 1;
    scaleAdjusted = true;
    renderScale();
  });
  const fullscreenTarget = dialog.querySelector(".media-viewer__shell");
  if (!document.fullscreenEnabled || !fullscreenTarget?.requestFullscreen) controls.fullscreen.hidden = true;
  controls.fullscreen.addEventListener("click", async () => {
    try { if (!document.fullscreenElement) await fullscreenTarget.requestFullscreen(); else await document.exitFullscreen(); }
    catch (_) { /* Fullscreen can be denied by the browser or embedding context. */ }
  });
  document.addEventListener("keydown", (event) => {
    if (!dialog.open) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      const forward = dialog.dataset.readingDirection === "rtl" ? "ArrowLeft" : "ArrowRight";
      navigate(event.key === forward ? "next" : "previous");
    }
  });
  stage.addEventListener("touchstart", (event) => {
    if (scale <= fitScale * 1.001 && event.touches.length === 1) touchStart = {x: event.touches[0].clientX, y: event.touches[0].clientY};
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStart === null || scale > fitScale * 1.001 || !event.changedTouches.length) return;
    const deltaX = event.changedTouches[0].clientX - touchStart.x;
    const deltaY = event.changedTouches[0].clientY - touchStart.y;
    if (Math.abs(deltaX) > 60 && Math.abs(deltaX) > Math.abs(deltaY) * 1.3) {
      const forward = dialog.dataset.readingDirection === "rtl" ? deltaX < 0 : deltaX > 0;
      navigate(forward ? "next" : "previous");
    }
    touchStart = null;
  }, { passive: true });
  stage.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "mouse" || event.button !== 0 || !stage.classList.contains("is-zoomed")) return;
    dragStart = {x: event.clientX, y: event.clientY, left: stage.scrollLeft, top: stage.scrollTop};
    stage.classList.add("is-dragging");
    stage.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  stage.addEventListener("pointermove", (event) => {
    if (!dragStart || !stage.hasPointerCapture(event.pointerId)) return;
    stage.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
    stage.scrollTop = dragStart.top - (event.clientY - dragStart.y);
  });
  const finishDrag = (event) => {
    if (!dragStart) return;
    dragStart = null;
    stage.classList.remove("is-dragging");
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
  };
  stage.addEventListener("pointerup", finishDrag);
  stage.addEventListener("pointercancel", finishDrag);
  [image, leftPage, rightPage].forEach((node) => node.addEventListener("load", () => { if (dialog.open && !scaleAdjusted) fit(); }));
  window.addEventListener("resize", () => { if (dialog.open) fit(); });
  const openFromHash = () => {
    if (!location.hash) return;
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target?.matches("a.media-viewer-trigger")) open(target);
  };
  window.addEventListener("hashchange", openFromHash);
  openFromHash();
})();
