console.log("🟢 main.js sa načítal!");

document.addEventListener("DOMContentLoaded", function () {
  // ✅ VITANIE
  const popup = document.getElementById("uvitanie-popup");
  if (popup) {
    setTimeout(() => popup.remove(), 6000);
    document.addEventListener("click", () => popup.remove(), { once: true });
  }

  // ✅ HĽADÁM KAPELU
  const showDopytBtn = document.querySelector("#show-dopyt-form");
  const formDopyt = document.querySelector("#form-hladam-kapelu");
  const closeDopytBtn = document.querySelector("#close-hladam-kapelu");

  if (showDopytBtn && formDopyt) {
    showDopytBtn.addEventListener("click", () => formDopyt.classList.add("open"));
    showDopytBtn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        formDopyt.classList.add("open");
      }
    });
  }

  if (closeDopytBtn && formDopyt) {
    closeDopytBtn.addEventListener("click", () => formDopyt.classList.remove("open"));
    window.addEventListener("click", (e) => {
      if (e.target === formDopyt) {
        formDopyt.classList.remove("open");
      }
    });
  }

  // ✅ REGISTRÁCIA UŽÍVATEĽA
  const registerBtn = document.getElementById('btn-register');
  const userFormPanel = document.getElementById('user-form-panel');
  const closeUserForm = document.getElementById('close-user-form');

  if (registerBtn && userFormPanel && closeUserForm) {
    registerBtn.addEventListener('click', () => userFormPanel.classList.add('open'));
    closeUserForm.addEventListener('click', () => userFormPanel.classList.remove('open'));
    window.addEventListener('click', (e) => {
      if (e.target === userFormPanel) {
        userFormPanel.classList.remove('open');
      }
    });
  }

  // ✅ REGISTRÁCIA Skupiny
  const showFormBtn = document.querySelector("#show-form");
  const formPanel = document.querySelector("#form-panel");
  const closeFormBtn = document.querySelector("#close-form");

  if (showFormBtn && formPanel && closeFormBtn) {
    showFormBtn.addEventListener("click", () => formPanel.classList.add("open"));
    closeFormBtn.addEventListener("click", () => formPanel.classList.remove("open"));
    window.addEventListener("click", function (e) {
      if (e.target === formPanel) {
        formPanel.classList.remove("open");
      }
    });
  }

// ✅ ÚPRAVA SKUPINY – prepínanie zobrazenia a formulára
  const editSkupinaBtn = document.querySelector("#editSkupinaBtn");
  const editSkupinaForm = document.querySelector("#editSkupinaForm");
  const udajeSkupina = document.querySelector("#udaje-zobraz-skupina");
  const cancelEditSkupina = document.querySelector("#cancelEditSkupina");

  if (editSkupinaBtn && editSkupinaForm && udajeSkupina && cancelEditSkupina) {
    editSkupinaBtn.addEventListener("click", function () {
      editSkupinaForm.style.display = "block";
      udajeSkupina.style.display = "none";
    });

    cancelEditSkupina.addEventListener("click", function () {
      editSkupinaForm.style.display = "none";
      udajeSkupina.style.display = "block";
    });
  }


  // ✅ INZERÁT
  const showInzeratBtn = document.querySelector("#show-inzerat");
  const formInzerat = document.querySelector("#form-inzerat");
  const closeInzeratBtn = document.querySelector("#close-inzerat");

  if (showInzeratBtn && formInzerat && closeInzeratBtn) {
    showInzeratBtn.addEventListener("click", () => formInzerat.classList.add("open"));
    closeInzeratBtn.addEventListener("click", () => formInzerat.classList.remove("open"));
    window.addEventListener("click", (e) => {
      if (e.target === formInzerat) {
        formInzerat.classList.remove("open");
      }
    });
  }

  // ✅ HESLO – prepínač
  const toggleHeslo = document.querySelector("#toggle-heslo");
  const hesloInput = document.querySelector("#heslo");

  if (toggleHeslo && hesloInput) {
    toggleHeslo.addEventListener("click", function () {
      const typ = hesloInput.type === "password" ? "text" : "password";
      hesloInput.type = typ;
      this.textContent = typ === "text" ? "🙈" : "👁️";
    });
  }

  // ✅ Výber iného nástroja
  const instrumentSelect = document.querySelector("#instrument");
  const ineBox = document.querySelector("#instrument-ine");

  if (instrumentSelect && ineBox) {
    instrumentSelect.addEventListener("change", function () {
      if (this.value === "ine") {
        ineBox.style.display = "block";
      } else {
        ineBox.style.display = "none";
        const input = document.querySelector("#instrument_dalsi");
        if (input) input.value = "";
      }
    });
  }

  // ✅ PRIHLÁSENIE
  const loginBtn = document.getElementById('btn-login');
  const loginModal = document.getElementById('modal-login');
  const closeLoginBtn = document.getElementById('close-login');

  if (loginBtn && loginModal && closeLoginBtn) {
    loginBtn.addEventListener('click', () => loginModal.classList.add('open'));
    closeLoginBtn.addEventListener('click', () => loginModal.classList.remove('open'));
    window.addEventListener('click', (e) => {
      if (e.target === loginModal) {
        loginModal.classList.remove('open');
      }
    });
  }

  // ✅ PROFIL
  const editBtn = document.getElementById('editButton');
  const cancelBtn = document.getElementById('cancelEdit');
  const zobraz = document.getElementById('udaje-zobraz');
  const form = document.getElementById('editForm');

  if (editBtn && cancelBtn && zobraz && form) {
    editBtn.addEventListener('click', () => {
      zobraz.style.display = 'none';
      form.style.display = 'block';
    });

    cancelBtn.addEventListener('click', () => {
      form.style.display = 'none';
      zobraz.style.display = 'block';
    });
  }

  console.log("✅ main.js načítaný!");
});

// ✅ RESPONSÍVNE MENU
function toggleMenu() {
  const nav = document.querySelector('.main-nav');
  nav.classList.toggle('active');
}
