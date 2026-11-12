(() => {
  "use strict";
  const dialog = document.querySelector("dialog.media-viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const image = dialog.querySelector("[data-viewer-image]");
  const caption = dialog.querySelector("[data-viewer-caption]");
  const position = dialog.querySelector("[data-viewer-position]");
  const stage = dialog.querySelector("[data-viewer-stage]");
  const controls = Object.fromEntries([...dialog.querySelectorAll("[data-viewer-action]")]
    .map((button) => [button.dataset.viewerAction, button]));
  let active = null;
  let previousFocus = null;
  let scale = 1;
  let fitScale = 1;
  let fitWidth = 0;
  let fitHeight = 0;
  let touchStart = null;
  const measureFit = () => {
    if (!image.naturalWidth || !image.naturalHeight) return false;
    fitScale = Math.min(1, stage.clientWidth / image.naturalWidth, stage.clientHeight / image.naturalHeight);
    fitWidth = image.naturalWidth * fitScale;
    fitHeight = image.naturalHeight * fitScale;
    return true;
  };
  const renderScale = () => {
    if (!fitWidth || !fitHeight) return;
    image.style.width = `${fitWidth * scale}px`;
    image.style.height = `${fitHeight * scale}px`;
    stage.classList.toggle("is-zoomed", scale > 1.001);
  };
  const fit = () => {
    scale = 1;
    measureFit();
    renderScale();
    stage.scrollTo(0, 0);
  };
  const open = (link) => {
    if (!link || !link.matches("a.media-viewer-trigger")) return;
    const wasClosed = !dialog.open;
    active = link;
    if (wasClosed) previousFocus = document.activeElement;
    image.src = link.href;
    image.alt = link.querySelector("img")?.alt || "";
    caption.textContent = link.dataset.viewerCaption || "";
    position.textContent = link.dataset.viewerPosition || "";
    controls.previous.disabled = !link.dataset.viewerPrevious;
    controls.next.disabled = !link.dataset.viewerNext;
    if (wasClosed) dialog.showModal();
    fit();
    if (wasClosed) controls.close.focus();
  };
  const close = () => { if (dialog.open) dialog.close(); };
  const navigate = (direction) => {
    if (!active) return;
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
  const zoom = (factor) => {
    scale = Math.max(1, Math.min(64, scale * factor));
    renderScale();
  };
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a.media-viewer-trigger");
    if (!link) return;
    event.preventDefault();
    open(link);
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  dialog.addEventListener("close", () => {
    image.removeAttribute("src");
    stage.classList.remove("is-zoomed");
    if (previousFocus?.isConnected) previousFocus.focus();
    active = null;
  });
  controls.close.addEventListener("click", close);
  controls.previous.addEventListener("click", () => navigate("previous"));
  controls.next.addEventListener("click", () => navigate("next"));
  controls["zoom-in"].addEventListener("click", () => zoom(1.25));
  controls["zoom-out"].addEventListener("click", () => zoom(0.8));
  controls.fit.addEventListener("click", fit);
  controls.actual.addEventListener("click", () => {
    if (!image.naturalWidth || !image.naturalHeight) return;
    measureFit();
    scale = 1 / fitScale;
    renderScale();
  });
  if (!document.fullscreenEnabled || !dialog.requestFullscreen) controls.fullscreen.hidden = true;
  controls.fullscreen.addEventListener("click", async () => {
    try { if (!document.fullscreenElement) await dialog.requestFullscreen(); else await document.exitFullscreen(); }
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
    if (scale <= 1.001 && event.touches.length === 1) touchStart = {x: event.touches[0].clientX, y: event.touches[0].clientY};
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStart === null || scale > 1.001 || !event.changedTouches.length) return;
    const deltaX = event.changedTouches[0].clientX - touchStart.x;
    const deltaY = event.changedTouches[0].clientY - touchStart.y;
    if (Math.abs(deltaX) > 60 && Math.abs(deltaX) > Math.abs(deltaY) * 1.3) {
      const forward = dialog.dataset.readingDirection === "rtl" ? deltaX < 0 : deltaX > 0;
      navigate(forward ? "next" : "previous");
    }
    touchStart = null;
  }, { passive: true });
  image.addEventListener("load", () => { if (dialog.open) fit(); });
  window.addEventListener("resize", () => { if (dialog.open) fit(); });
  const openFromHash = () => {
    if (!location.hash) return;
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target?.matches("a.media-viewer-trigger")) open(target);
  };
  window.addEventListener("hashchange", openFromHash);
  openFromHash();
})();
