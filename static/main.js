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

// sidebar rozbalovacie menu – zľava, bez overlayu
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('menu-toggle');
  const panel  = document.getElementById('user-menu');
  if (!toggle || !panel) return;

  const closeBtn = panel.querySelector('.offcanvas-close');

  function openPanel(){
    panel.classList.add('open');
    toggle.setAttribute('aria-expanded','true');
    panel.setAttribute('aria-hidden','false');
    // ak nechceš zamknúť scroll pri otvorenom paneli, tento riadok vyhoď:
    document.body.style.overflow = 'hidden';
  }
  function closePanel(){
    panel.classList.remove('open');
    toggle.setAttribute('aria-expanded','false');
    panel.setAttribute('aria-hidden','true');
    document.body.style.overflow = '';
    toggle.focus?.({preventScroll:true});
  }
  const isOpen = () => panel.classList.contains('open');

  toggle.addEventListener('click', () => isOpen() ? closePanel() : openPanel());
  closeBtn?.addEventListener('click', closePanel);                    // X
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen()) closePanel(); });
  // žiadne overlay kliky, žiadne stmavenie
});
