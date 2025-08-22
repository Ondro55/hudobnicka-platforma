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

(function () {
  const $ = (sel, root = document) => root.querySelector(sel);

  function openModal() {
    const m = $('#sprava-modal');
    if (!m) return;
    m.hidden = false;
    m.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }

  function closeModal() {
    const m = $('#sprava-modal');
    if (!m) return;
    m.hidden = true;
    m.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  // Delegovaný click na tlačidlá "Reagovať"
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-open="sprava-modal"]');
    if (!btn) return;

    const form = $('#sprava-form');
    if (!form) return;

    // data-* z tlačidla
    const id     = btn.dataset.dopytId    || '';
    const typ    = btn.dataset.dopytTyp   || 'Dopyt';
    const datum  = btn.dataset.dopytDatum || '';
    const miesto = btn.dataset.dopytMiesto|| '';
    const meno   = btn.dataset.dopytMeno  || '';
    const email  = btn.dataset.dopytEmail || '';

    const parts = [typ, datum, miesto].filter(Boolean);
    const subject = `Reakcia na dopyt: ${parts.join(' – ')}`;
    const bodyText =
`Dobrý deň ${meno || ''},

reagujem na Váš dopyt (${parts.join(' – ')}).
Som k dispozícii, rád/rada upresním detaily (repertoár, technika, dĺžka vystúpenia).

Ďakujem a teším sa na odpoveď.
`;

    // Predvyplnenie – podpor obidve schémy názvov polí
    form.elements['dopyt_id']   && (form.elements['dopyt_id'].value   = id);
    form.elements['subject']    && (form.elements['subject'].value    = subject);
    form.elements['message']    && (form.elements['message'].value    = bodyText);
    form.elements['to']         && (form.elements['to'].value         = email);

    // pre spravy.odoslat (náš backend)
    form.elements['kontekst']    && (form.elements['kontekst'].value    = 'dopyt');
    form.elements['kontekst_id'] && (form.elements['kontekst_id'].value = id);
    form.elements['komu_email']  && (form.elements['komu_email'].value  = email);
    form.elements['obsah']       && (form.elements['obsah'].value       = bodyText);

    openModal();
    setTimeout(() => { form.elements['subject']?.focus(); }, 0);
  });

  // Zavrieť (X alebo tlačidlo s data-close)
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-close="sprava-modal"]')) {
      e.preventDefault();
      closeModal();
    }
  });

  // ESC zatvorí modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  // Po odoslaní (klasický POST + redirect) modal hneď zavri
  document.addEventListener('submit', (e) => {
    const form = e.target.closest('#sprava-form');
    if (!form) return;
    closeModal();
  });
})();

