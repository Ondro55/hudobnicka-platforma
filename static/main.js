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

document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-toggle-password]');
  if (!btn) return;
  const sel = btn.getAttribute('data-toggle-password');
  const input = document.querySelector(sel);
  if (!input) return;
  input.type = (input.type === 'password') ? 'text' : 'password';
});

// sidebar rozbalovacie menu //
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('menu-toggle');
  const panel  = document.getElementById('user-menu');
  if (!toggle || !panel) return;

  // vytvoríme polopriesvitné pozadie (overlay), ak ešte nie je
  let overlay = document.getElementById('user-menu-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'user-menu-overlay';
    Object.assign(overlay.style, {
      position:'fixed', inset:'0', background:'rgba(0,0,0,.35)',
      opacity:'0', pointerEvents:'none', transition:'opacity .2s ease', zIndex:'1199'
    });
    document.body.appendChild(overlay);
  }

  function openPanel(){
    panel.classList.add('open');
    overlay.style.opacity = '1';
    overlay.style.pointerEvents = 'auto';
    toggle.setAttribute('aria-expanded','true');
    panel.setAttribute('aria-hidden','false');
    // fokus do panela
    const focusable = panel.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    focusable?.focus({preventScroll:true});
    document.body.style.overflow = 'hidden';
  }
  function closePanel(){
    panel.classList.remove('open');
    overlay.style.opacity = '0';
    overlay.style.pointerEvents = 'none';
    toggle.setAttribute('aria-expanded','false');
    panel.setAttribute('aria-hidden','true');
    toggle.focus({preventScroll:true});
    document.body.style.overflow = '';
  }
  function isOpen(){ return panel.classList.contains('open'); }

  toggle.addEventListener('click', () => isOpen() ? closePanel() : openPanel());
  overlay.addEventListener('click', closePanel);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) closePanel(); });
});
