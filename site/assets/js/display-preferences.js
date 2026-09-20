(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var controls = document.querySelector("[data-display-controls]");
  if (!controls) return;

  var themeButtons = controls.querySelectorAll("[data-set-theme]");
  var sizeButtons = controls.querySelectorAll("[data-set-text-size]");

  function setState(attribute, value) {
    if (value) body.setAttribute(attribute, value);
  }

  function updatePressed(selector, value) {
    controls.querySelectorAll(selector).forEach(function (button) {
      button.setAttribute("aria-pressed", button.getAttribute(selector.slice(1, -1)) === value ? "true" : "false");
    });
  }

  function setTheme(value) {
    setState("data-theme", value);
    updatePressed("[data-set-theme]", value);
  }

  function setTextSize(value) {
    setState("data-text-size", value);
    updatePressed("[data-set-text-size]", value);
  }

  themeButtons.forEach(function (button) { button.addEventListener("click", function () { setTheme(button.getAttribute("data-set-theme")); }); });
  sizeButtons.forEach(function (button) { button.addEventListener("click", function () { setTextSize(button.getAttribute("data-set-text-size")); }); });

  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  setTheme(media && media.matches ? "dark" : (body.getAttribute("data-theme") || "light"));
  setTextSize(body.getAttribute("data-text-size") || "standard");
  controls.hidden = false;
}());
