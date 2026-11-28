/* Shared chrome behavior; no network requests or dependencies. */
(function () {
  'use strict';
  var root = document.documentElement;
  var theme = 'light';
  try {
    if (localStorage.getItem('cg-theme') === 'dark') theme = 'dark';
  } catch (_) { /* Storage is optional. */ }

  function applyTheme(next, persist) {
    theme = next;
    root.setAttribute('data-theme', theme);
    var themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = theme === 'dark' ? '#17171b' : '#f9f9f8';
    document.querySelectorAll('.theme-toggle [data-theme]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.theme === theme));
    });
    if (persist) {
      try { localStorage.setItem('cg-theme', theme); } catch (_) {}
    }
  }

  function updateSectionNavigation() {
    if (!document.body.classList.contains('agents-page')) return;
    var atDevTools = location.hash === '#get-started';
    document.querySelectorAll('[data-navigation="agents"], [data-navigation="dev"]').forEach(function (link) {
      var isDev = link.dataset.navigation === 'dev';
      if (isDev === atDevTools) link.setAttribute('aria-current', isDev ? 'location' : 'page');
      else link.removeAttribute('aria-current');
    });
  }

  // Apply before the stylesheet paints so the previous choice does not flash.
  applyTheme(theme, false);
  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(theme, false);
    document.querySelectorAll('.theme-toggle [data-theme]').forEach(function (button) {
      button.addEventListener('click', function () { applyTheme(button.dataset.theme, true); });
    });
    updateSectionNavigation();
    window.addEventListener('hashchange', updateSectionNavigation);
  });
})();
