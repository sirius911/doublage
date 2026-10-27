// Éditeur : affiche sur l'image le texte de la phrase en cours de lecture, et permet de le corriger
// sur l'image (vidéo en pause) ou dans la liste. Les corrections sont enregistrées automatiquement.
(() => {
  const video = document.getElementById("video");
  const surImage = document.getElementById("sur-image");
  const etatEnregistrement = document.getElementById("enregistrement");
  const phrases = [...document.querySelectorAll("#phrases li")].map((li) => ({
    li,
    id: li.dataset.id,
    debut: parseFloat(li.dataset.debut),
    fin: parseFloat(li.dataset.fin),
    texte: li.querySelector(".texte"),
    minuterie: null,
  }));
  let enCours = null;
  let finExtrait = null;  // « ▶ Original » : la vidéo s'arrête à la fin de la phrase

  // --- Affichage sur l'image ---

  function phraseA(t) {
    return phrases.find((p) => p.debut <= t && t < p.fin) || null;
  }

  function afficher() {
    const p = phraseA(video.currentTime);
    if (p === enCours) return;
    if (document.activeElement === surImage) surImage.blur();  // enregistre la phrase quittée
    if (enCours) enCours.li.classList.remove("en-cours");
    enCours = p;
    surImage.hidden = !p;
    surImage.textContent = p ? p.texte.textContent : "";
    if (p) p.li.classList.add("en-cours");
    // Pendant la lecture, la liste suit la phrase en cours (sauf si on y corrige un texte).
    if (p && !video.paused && !p.li.parentElement.contains(document.activeElement)) {
      p.li.scrollIntoView({ block: "nearest" });
    }
  }

  // Correction sur l'image possible seulement à l'arrêt (sinon le texte change sous le curseur).
  function modeEdition() {
    const edition = video.paused;
    try {
      surImage.contentEditable = edition ? "plaintext-only" : "false";
    } catch {
      surImage.contentEditable = edition ? "true" : "false";  // navigateur ancien
    }
    surImage.classList.toggle("modifiable", edition);
  }

  // timeupdate n'arrive que ~4 fois par seconde : pendant la lecture, on suit chaque image.
  function suivre() {
    if (finExtrait !== null && video.currentTime >= finExtrait) {
      video.pause();
      finExtrait = null;
    }
    afficher();
    if (!video.paused) requestAnimationFrame(suivre);
  }
  video.addEventListener("play", () => { modeEdition(); suivre(); });
  video.addEventListener("pause", () => { finExtrait = null; modeEdition(); });
  video.addEventListener("seeked", afficher);
  video.addEventListener("timeupdate", afficher);

  // --- Enregistrement automatique ---

  async function enregistrer(p) {
    clearTimeout(p.minuterie);
    p.minuterie = null;
    const texte = p.texte.textContent;
    etatEnregistrement.textContent = "Enregistrement…";
    try {
      const r = await fetch(`/projets/${PROJET}/phrases/${p.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texte }),
      });
      if (!r.ok) throw new Error(r.status);
      etatEnregistrement.textContent = "Enregistré.";
      etatEnregistrement.className = "";
      p.li.dataset.etat = (await r.json()).etat;
      majVoix(p);
    } catch (e) {
      etatEnregistrement.textContent = "Échec de l'enregistrement, réessayez (connexion ?).";
      etatEnregistrement.className = "erreur";
    }
  }

  function modifie(p) {
    clearTimeout(p.minuterie);
    p.minuterie = setTimeout(() => enregistrer(p), 800);
    etatEnregistrement.textContent = "Modifié…";
  }

  // Entrée valide la phrase au lieu d'insérer un retour à la ligne.
  function entreeValide(element) {
    element.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); element.blur(); }
    });
  }

  surImage.addEventListener("input", () => {
    if (!enCours) return;
    enCours.texte.textContent = surImage.textContent;
    modifie(enCours);
  });
  surImage.addEventListener("blur", () => {
    if (enCours && enCours.minuterie) enregistrer(enCours);
  });
  entreeValide(surImage);

  // Clic sur une phrase : la vidéo se place à son début (lecture ou pause conservée). Un clic dans
  // le texte de la phrase déjà en cours ne déplace pas la vidéo, pour pouvoir corriger tranquillement.
  function allerA(p) {
    video.currentTime = p.debut;
    afficher();
  }

  // --- Écoute et génération de la voix d'une phrase ---

  const lecteurVoix = new Audio();
  const ETATS = { synthetisee: "voix à jour", modifiee: "texte modifié : voix à régénérer" };

  function voixAJour(p) {
    return "voix" in p.li.dataset && p.li.dataset.etat === "synthetisee";
  }

  function majVoix(p) {
    p.etat.textContent = "voix" in p.li.dataset ? (ETATS[p.li.dataset.etat] || "") : "";
  }

  function ecouterOriginal(p) {
    lecteurVoix.pause();
    allerA(p);
    finExtrait = p.fin;
    video.play();
  }

  function ecouterVoix(p) {
    video.pause();
    lecteurVoix.src = `/projets/${PROJET}/phrases/${p.id}/voix?v=${Date.now()}`;  // pas de cache
    lecteurVoix.play();
  }

  // « ▶ Voix » : joue la voix si elle est à jour, sinon la crée d'abord (texte nouveau ou corrigé).
  async function voix(p) {
    if (p.minuterie) await enregistrer(p);  // la voix doit suivre le texte corrigé
    if (voixAJour(p)) { ecouterVoix(p); return; }
    p.boutonVoix.disabled = true;
    document.documentElement.classList.add("travail");
    p.etat.textContent = "Création de la voix…";
    try {
      const r = await fetch(`/projets/${PROJET}/phrases/${p.id}/voix`, { method: "POST" });
      if (!r.ok) throw new Error(r.status);
      p.li.dataset.voix = "";
      p.li.dataset.etat = (await r.json()).etat;
      majVoix(p);
      ecouterVoix(p);
    } catch (e) {
      p.etat.textContent = "Échec de la génération.";
    } finally {
      p.boutonVoix.disabled = false;
      document.documentElement.classList.remove("travail");
    }
  }

  for (const p of phrases) {
    p.boutonVoix = p.li.querySelector(".voix");
    p.etat = p.li.querySelector(".etat");
    majVoix(p);
    p.li.querySelector(".original").addEventListener("click", () => ecouterOriginal(p));
    p.boutonVoix.addEventListener("click", () => voix(p));

    p.li.addEventListener("click", (e) => {
      if (e.target.closest(".actions")) return;
      if (e.target.closest(".aller") || p !== enCours) allerA(p);
    });
    p.texte.addEventListener("input", () => {
      if (p === enCours) surImage.textContent = p.texte.textContent;
      modifie(p);
    });
    p.texte.addEventListener("blur", () => { if (p.minuterie) enregistrer(p); });
    entreeValide(p.texte);
  }

  // Fin de la génération de la vidéo doublée : on rafraîchit la section et l'état des phrases
  // sans recharger la page (la position de la vidéo et les corrections en cours sont conservées).
  window.rafraichirDoublage = async () => {
    const page = new DOMParser().parseFromString(await (await fetch(location.href)).text(), "text/html");
    document.getElementById("doublage").replaceWith(page.getElementById("doublage"));
    for (const p of phrases) {
      const li = page.querySelector(`#phrases li[data-id="${p.id}"]`);
      if (!li) continue;
      p.li.dataset.etat = li.dataset.etat;
      if ("voix" in li.dataset) p.li.dataset.voix = "";
      majVoix(p);
    }
  };

  window.addEventListener("beforeunload", (e) => {
    if (phrases.some((p) => p.minuterie !== null)) e.preventDefault();  // correction pas encore envoyée
  });

  modeEdition();
  afficher();
})();
