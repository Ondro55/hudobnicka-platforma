// vykakovacie_okno.js

document.addEventListener("DOMContentLoaded", function () {
  const flashContainer = document.getElementById("flash-container");
  if (flashContainer) {
    //Po 3 sekundách začni schovávať
    setTimeout(() => {
      flashContainer.style.opacity = "0";
      setTimeout(() => {
        flashContainer.remove();
      }, 500); // počkaj ešte chvíľu na animáciu
    }, 3000);

    // Alebo hneď keď sa klikne niekam
    document.addEventListener("click", () => {
      if (flashContainer) {
        flashContainer.remove();
      }
    });
  }
});
