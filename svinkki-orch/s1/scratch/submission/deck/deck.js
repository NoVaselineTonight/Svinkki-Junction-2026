// One slide at a time, scaled to the window. Arrows, space, click or swipe to move; F for full screen.
(function () {
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var i = Math.max(0, Math.min(slides.length - 1, (parseInt(location.hash.slice(1), 10) || 1) - 1));
  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    slides.forEach(function (el) { el.style.transform = 'scale(' + s + ')'; });
  }
  function show(n) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (el, j) { el.classList.toggle('on', j === i); });
    history.replaceState(null, '', '#' + (i + 1));
  }
  document.addEventListener('keydown', function (e) {
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].indexOf(e.key) >= 0) { e.preventDefault(); show(i + 1); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp'].indexOf(e.key) >= 0) { e.preventDefault(); show(i - 1); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 'f' || e.key === 'F') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); }
  });
  document.addEventListener('click', function (e) { show(e.clientX < window.innerWidth / 3 ? i - 1 : i + 1); });
  var x0 = null;
  document.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
  document.addEventListener('touchend', function (e) {
    if (x0 === null) return;
    var dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 40) show(dx < 0 ? i + 1 : i - 1);
  });
  window.addEventListener('resize', fit);
  fit(); show(i);
})();
