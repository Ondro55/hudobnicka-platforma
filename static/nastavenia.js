(function(){
  const root = document.documentElement;

  // cookie helpers
  function setCookie(name, value, days){
    const exp = new Date(Date.now() + days*864e5).toUTCString();
    document.cookie = name + '=' + encodeURIComponent(value) + '; Path=/; SameSite=Lax; Expires=' + exp;
  }
  function getCookie(name){
    const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[-/\\^$*+?.()|[\]{}]/g,'\\$&') + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function loadPrefs(){ try { return JSON.parse(getCookie('mz_prefs') || '{}'); } catch(_){ return {}; } }
  function savePrefs(p){ setCookie('mz_prefs', JSON.stringify(p), 365); }

  function appliedTheme(){ return root.getAttribute('data-theme') || 'system'; }
  function applyTheme(theme){ if (theme === 'system' || !theme) root.removeAttribute('data-theme'); else root.setAttribute('data-theme', theme); }
  function syncRadios(theme){ document.querySelectorAll('input[name="theme"]').forEach(r => r.checked = (r.value === theme)); }

  document.addEventListener('DOMContentLoaded', function(){
    const themeNow = appliedTheme();
    syncRadios(themeNow);
    setTimeout(() => syncRadios(appliedTheme()), 0);
  });

  document.addEventListener('change', async function(e){
    const r = e.target.closest('input[name="theme"]');
    if (!r) return;

    const val = r.value; // system | blue | green | red | light | dark
    console.log('Switch theme →', val);

    // 1) okamžitý vizuál
    applyTheme(val);
    syncRadios(val);

    // 2) cookie (lokálna preferencia pre early load)
    const prefs = loadPrefs(); prefs.theme = val; savePrefs(prefs);

    // 3) AUTOSAVE do DB (bez tlačidla Uložiť)
    try {
      const form = document.getElementById('form-vzhlad');
      const url = (form && form.getAttribute('action')) || '/nastavenia/uloz';
      const fd = new FormData();
      fd.append('theme', val);

      const res = await fetch(url, {
        method: 'POST',
        body: fd,
        credentials: 'same-origin' // nech sa prenesú cookies a chytí sa Set-Cookie z odpovede
      });

      if (!res.ok) throw new Error('HTTP ' + res.status);

      // Pozn.: server vracia redirect; fetch ho síce nasleduje, ale stránku nemeníme.
      // Set-Cookie z backendu sa aj tak uloží. Všetko zostane zosynchronizované.
    } catch (err) {
      console.warn('Autosave theme failed:', err);
      // Nepovinné: tu môžeš ukázať toast a prípadne vrátiť na pôvodnú tému z cookie/DB.
    }
  });
})();
