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

// Auto-hide flash správy (bolo vo vyskakovacie_okno.js)
document.addEventListener("DOMContentLoaded", () => {
  const flashContainer = document.getElementById("flash-container");
  if (!flashContainer) return;

  const close = () => { if (flashContainer && flashContainer.parentNode) flashContainer.remove(); };

  // po 3 s jemne vyblednú a zmiznú
  setTimeout(() => {
    flashContainer.style.opacity = "0";
    setTimeout(close, 500); // necháme prebehnúť prechod
  }, 3000);

  // alebo hneď pri prvom kliknutí kdekoľvek
  document.addEventListener("click", close, { once: true });
});

// (voliteľné) Auto-hide uvítací box, ak ho zobrazuješ
document.addEventListener("DOMContentLoaded", () => {
  const up = document.getElementById("uvitanie-popup");
  if (up) setTimeout(() => { if (up.parentNode) up.remove(); }, 6000);
});
