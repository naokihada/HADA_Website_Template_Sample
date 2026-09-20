(function () {
  "use strict";

  var body = document.body;
  var controls = document.querySelector("[data-display-controls]");
  if (!controls) return;

  var themeButtons = controls.querySelectorAll("[data-set-theme]");
  var sizeButtons = controls.querySelectorAll("[data-set-text-size]");
  var modeButtons = controls.querySelectorAll("[data-set-mode]");
  var persistenceEnabled = body.getAttribute("data-display-persistence") === "true";
  var storageKey = body.getAttribute("data-display-storage-key") || "hada.display.v1";
  var allowedThemes = ["light", "dark"];
  var allowedSizes = ["standard", "large", "xlarge"];
  var allowedModes = ["standard", "play", "reading"];

  function allowed(value, values, fallback) {
    return values.indexOf(value) >= 0 ? value : fallback;
  }

  function updatePressed(selector, attribute, value) {
    controls.querySelectorAll(selector).forEach(function (button) {
      button.setAttribute("aria-pressed", button.getAttribute(attribute) === value ? "true" : "false");
    });
  }

  function applyState(state) {
    var theme = allowed(state.theme, allowedThemes, body.getAttribute("data-theme") || "light");
    var textSize = allowed(state.text_size, allowedSizes, body.getAttribute("data-text-size") || "standard");
    var mode = allowed(state.mode, allowedModes, body.getAttribute("data-mode") || "standard");
    body.setAttribute("data-theme", theme);
    body.setAttribute("data-text-size", textSize);
    body.setAttribute("data-mode", mode);
    updatePressed("[data-set-theme]", "data-set-theme", theme);
    updatePressed("[data-set-text-size]", "data-set-text-size", textSize);
    updatePressed("[data-set-mode]", "data-set-mode", mode);
  }

  function readState() {
    if (!persistenceEnabled || !window.localStorage) return {};
    try {
      var parsed = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function saveState() {
    if (!persistenceEnabled || !window.localStorage) return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({
        schema_version: "1",
        theme: body.getAttribute("data-theme") || "light",
        text_size: body.getAttribute("data-text-size") || "standard",
        mode: body.getAttribute("data-mode") || "standard"
      }));
    } catch (error) {
      // Private browsing and storage quotas must not break the page.
    }
  }

  function setTheme(value) {
    applyState({ theme: value, text_size: body.getAttribute("data-text-size"), mode: body.getAttribute("data-mode") });
    saveState();
  }

  function setTextSize(value) {
    applyState({ theme: body.getAttribute("data-theme"), text_size: value, mode: body.getAttribute("data-mode") });
    saveState();
  }

  function setMode(value) {
    applyState({ theme: body.getAttribute("data-theme"), text_size: body.getAttribute("data-text-size"), mode: value });
    saveState();
  }

  themeButtons.forEach(function (button) { button.addEventListener("click", function () { setTheme(button.getAttribute("data-set-theme")); }); });
  sizeButtons.forEach(function (button) { button.addEventListener("click", function () { setTextSize(button.getAttribute("data-set-text-size")); }); });
  modeButtons.forEach(function (button) { button.addEventListener("click", function () { setMode(button.getAttribute("data-set-mode")); }); });

  var saved = readState();
  if (!saved.theme) {
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    saved.theme = media && media.matches ? "dark" : body.getAttribute("data-theme") || "light";
  }
  applyState(saved);
  controls.hidden = false;
}());
