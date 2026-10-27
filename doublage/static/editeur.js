// Éditeur : affiche sur l'image le texte de la phrase en cours de lecture.
(() => {
  const video = document.getElementById("video");
  const surImage = document.getElementById("sur-image");
  const phrases = [...document.querySelectorAll("#phrases li")].map((li) => ({
    li,
    debut: parseFloat(li.dataset.debut),
    fin: parseFloat(li.dataset.fin),
    texte: li.querySelector(".texte"),
  }));
  let enCours = null;

  function phraseA(t) {
    return phrases.find((p) => p.debut <= t && t < p.fin) || null;
  }

  function afficher() {
    const p = phraseA(video.currentTime);
    if (p === enCours) return;
    if (enCours) enCours.li.classList.remove("en-cours");
    enCours = p;
    surImage.hidden = !p;
    surImage.textContent = p ? p.texte.textContent : "";
    if (p) p.li.classList.add("en-cours");
  }

  // timeupdate n'arrive que ~4 fois par seconde : pendant la lecture, on suit chaque image.
  function suivre() {
    afficher();
    if (!video.paused) requestAnimationFrame(suivre);
  }
  video.addEventListener("play", suivre);
  video.addEventListener("seeked", afficher);
  video.addEventListener("timeupdate", afficher);
  afficher();
})();
