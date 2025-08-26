// static/main.js

// Helpers
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

// App init
document.addEventListener('DOMContentLoaded', () => {
  // hamburger (záloha popri inline toggleMenu v base.html)
  const ham = $('.hamburger');
  if (ham){ ham.addEventListener('click', () => $('.main-nav')?.classList.toggle('active')); }

  // auto-open ?open=dopyt (použije window.openModal z base.html)
  try {
    const params = new URLSearchParams(location.search);
    if (params.get('open') === 'dopyt' && window.openModal) window.openModal('#dopyt-form');
  } catch(_) {}
});
