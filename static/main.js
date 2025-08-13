// ======================
// 🧰 Helpers
// ======================
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
const on = (el, ev, fn) => el && el.addEventListener(ev, fn);
const show = el => el && el.classList.add('open');
const hide = el => el && el.classList.remove('open');
const closeAll = () => $$('.form-panel.open').forEach(hide);

// hamburger
function toggleMenu(){ const n=$('.main-nav'); if(n) n.classList.toggle('active'); }
window.toggleMenu = toggleMenu;

// ======================
// 🚀 Init
// ======================
document.addEventListener('DOMContentLoaded', () => {
  // ------- DOPYT (Nájdi si kapelu) -------
  const dopytBtn   = $('#show-dopyt-form');
  const dopytPanel = $('#form-hladam-kapelu');
  const dopytClose = $('#close-hladam-kapelu');

  if (dopytBtn && dopytPanel) {
    on(dopytBtn, 'click', (e)=>{ e.preventDefault(); closeAll(); show(dopytPanel); });
    on(dopytBtn, 'keydown', (e)=>{
      if (e.key==='Enter' || e.key===' ') { e.preventDefault(); closeAll(); show(dopytPanel); }
    });
  }
  if (dopytPanel) {
    on(dopytPanel, 'click', (e)=>{ if(e.target===dopytPanel) hide(dopytPanel); });
    on(dopytClose, 'click', ()=> hide(dopytPanel));
  }

  // ------- PRIHLÁSENIE -------
  const btnLoginHdr = $('#btn-login');           // v hlavičke
  const loginPanel  = $('#modal-login');
  const closeLogin  = $('#close-login');

  if (btnLoginHdr && loginPanel) {
    on(btnLoginHdr, 'click', (e)=>{ e.preventDefault(); closeAll(); show(loginPanel); });
  }
  // odkazy vo vnútri stránok (už bez ID)
  $$('.open-login').forEach(a => on(a, 'click', (e)=>{ e.preventDefault(); closeAll(); show(loginPanel); }));

  if (loginPanel) {
    on(loginPanel, 'click', (e)=>{ if (e.target===loginPanel) hide(loginPanel); });
    on(closeLogin, 'click', ()=> hide(loginPanel));
  }

  // ------- REGISTRÁCIA -------
  const btnRegHdr = $('#btn-register');          // v hlavičke
  const regPanel  = $('#user-form-panel');
  const closeReg  = $('#close-user-form');

  if (btnRegHdr && regPanel) {
    on(btnRegHdr, 'click', (e)=>{ e.preventDefault(); closeAll(); show(regPanel); });
  }
  $$('.open-register').forEach(a => on(a, 'click', (e)=>{ e.preventDefault(); closeAll(); show(regPanel); }));

  if (regPanel) {
    on(regPanel, 'click', (e)=>{ if (e.target===regPanel) hide(regPanel); });
    on(closeReg, 'click', ()=> hide(regPanel));
  }

  // ------- Šedé linky pre neprihlásených -------
  $$('.disabled-link').forEach(a => on(a, 'click', (e)=>{
    e.preventDefault();
    closeAll();
    show(loginPanel);
  }));

  // ------- Auto-open z body[data-zobraz] -------
  const flag = document.body.getAttribute('data-zobraz');
  if (flag==='prihlasenie' && loginPanel){ closeAll(); show(loginPanel); }
  if (flag==='uzivatel'    && regPanel)  { closeAll(); show(regPanel);  }

  // ESC zatvorí ktorýkoľvek otvorený panel
  on(document, 'keydown', (e)=>{ if (e.key==='Escape') closeAll(); });
});
