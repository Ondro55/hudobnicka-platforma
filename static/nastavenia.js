(function(){
  const root = document.documentElement;

  // --- helpers: cookie get/set ---
  function setCookie(name, value, days){
    const expires = new Date(Date.now() + (days*864e5)).toUTCString();
    document.cookie = name + '=' + encodeURIComponent(value) + '; Path=/; SameSite=Lax; Expires=' + expires;
  }
  function getCookie(name){
    const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[-/\\^$*+?.()|[\]{}]/g,'\\$&') + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }

  // --- načítaj prefs JSON ---
  function loadPrefs(){
    try { return JSON.parse(getCookie('mz_prefs') || '{}'); } catch(_){ return {}; }
  }
  function savePrefs(p){
    setCookie('mz_prefs', JSON.stringify(p), 365);
  }

  // --- TÉMA: živé prepínanie ---
  const themeRadios = document.querySelectorAll('input[name="theme"]');
  if (themeRadios.length){
    themeRadios.forEach(r => {
      r.addEventListener('change', () => {
        const theme = r.value;            // system | light | dark | blue
        // okamžité vizuálne prepnutie
        if (theme === 'system') {
          root.removeAttribute('data-theme');
        } else {
          root.setAttribute('data-theme', theme);
        }
        // uložiť do cookie Preferencií
        const prefs = loadPrefs();
        prefs.theme = theme;
        savePrefs(prefs);
      });
    });
  }

  // --- (voliteľné) predvyplnenie výberu z cookie pri príchode
  const prefs = loadPrefs();
  if (prefs.theme){
    const current = document.querySelector('input[name="theme"][value="'+prefs.theme+'"]');
    if (current) current.checked = true;
  }
})();
