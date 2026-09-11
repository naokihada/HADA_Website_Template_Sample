(() => {
  const DEFAULT_SECONDS = 180;
  const MAX_SECONDS = 99 * 60 + 59;
  const display = document.querySelector("[data-timer-display]");
  const minutesInput = document.querySelector("#minutes");
  const secondsInput = document.querySelector("#seconds");
  const startButton = document.querySelector("[data-action='start']");
  const pauseButton = document.querySelector("[data-action='pause']");
  const resetButton = document.querySelector("[data-action='reset']");
  const notifyButton = document.querySelector("[data-action='notify']");
  const installButton = document.querySelector("[data-action='install']");
  const installHelp = document.querySelector("[data-install-help]");
  const status = document.querySelector("[data-timer-status]");
  let remaining = DEFAULT_SECONDS;
  let endAt = null;
  let intervalId = null;
  let completed = false;
  let deferredInstallPrompt = null;

  const format = (value) => `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  const setStatus = (message) => { status.textContent = message; };
  const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  const showInstallHelp = () => {
    if (isStandalone()) return;
    const isAppleMobile = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    installHelp.textContent = isAppleMobile
      ? "To install this timer, use Safari Share, then Add to Home Screen."
      : "To install this timer, use your browser menu and choose Install or Add to Home Screen.";
    installHelp.hidden = false;
  };
  const hideInstallUi = () => { installButton.hidden = true; installHelp.hidden = true; deferredInstallPrompt = null; };
  const readInputs = () => {
    const minutes = Math.min(99, Math.max(0, Number(minutesInput.value || 0)));
    const seconds = Math.min(59, Math.max(0, Number(secondsInput.value || 0)));
    return Math.min(MAX_SECONDS, Math.floor(minutes) * 60 + Math.floor(seconds));
  };
  const writeInputs = (value) => { minutesInput.value = Math.floor(value / 60); secondsInput.value = value % 60; };
  const render = () => { display.textContent = format(remaining); document.title = `${format(remaining)} — HADA Timer`; };

  const beep = () => {
    try {
      const context = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.25);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.25);
    } catch (_) {
      setStatus("Timer complete. Audio is unavailable in this browser.");
    }
  };

  const notify = async () => {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.showNotification("HADA Timer", { body: "Your timer is complete.", tag: "hada-timer-complete" });
    } catch (_) {
      setStatus("Timer complete. Local notification is unavailable.");
    }
  };

  const finish = () => {
    clearInterval(intervalId); intervalId = null; endAt = null; remaining = 0; completed = true;
    render(); beep(); notify(); setStatus("Complete");
  };
  const tick = () => { if (endAt !== null) { remaining = Math.max(0, Math.ceil((endAt - Date.now()) / 1000)); render(); if (remaining === 0) finish(); } };
  const start = () => {
    if (endAt === null) remaining = readInputs();
    if (remaining <= 0) return setStatus("Set a duration before starting.");
    completed = false; endAt = Date.now() + remaining * 1000; clearInterval(intervalId); intervalId = setInterval(tick, 250); setStatus("Running"); tick();
  };
  const pause = () => { if (endAt !== null) { tick(); endAt = null; clearInterval(intervalId); intervalId = null; setStatus("Paused"); } else if (!completed) start(); };
  const reset = () => { clearInterval(intervalId); intervalId = null; endAt = null; remaining = DEFAULT_SECONDS; completed = false; writeInputs(remaining); render(); setStatus("Ready"); };

  startButton.addEventListener("click", start);
  pauseButton.addEventListener("click", pause);
  resetButton.addEventListener("click", reset);
  [minutesInput, secondsInput].forEach((input) => input.addEventListener("input", () => { if (endAt === null) { remaining = readInputs(); completed = false; render(); setStatus("Ready"); } }));
  notifyButton.addEventListener("click", async () => {
    if (!("Notification" in window)) return setStatus("Notifications are not supported here.");
    const permission = await Notification.requestPermission();
    setStatus(permission === "granted" ? "Notifications enabled" : "Notifications not enabled");
  });
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    installButton.hidden = false;
    installHelp.hidden = true;
  });
  installButton.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    if (choice.outcome === "accepted") setStatus("Install requested");
  });
  window.addEventListener("appinstalled", () => { hideInstallUi(); setStatus("Timer installed"); });
  window.matchMedia("(display-mode: standalone)").addEventListener?.("change", (event) => { if (event.matches) hideInstallUi(); });
  window.addEventListener("beforeunload", () => clearInterval(intervalId));
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => setStatus("Timer ready; offline support unavailable."));
  reset();
  if (isStandalone()) hideInstallUi();
  else window.setTimeout(() => { if (!deferredInstallPrompt) showInstallHelp(); }, 1500);
})();
