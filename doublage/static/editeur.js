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
    surImage.hidden = !p || !p.texte.textContent.trim();  // rien à afficher pour une phrase effacée
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
    if (!p.texte.textContent.trim()) p.texte.textContent = "";  // phrase effacée (affiche son indication)
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

  // Le petit bouton ↺ n'apparaît que si le texte diffère de la transcription d'origine.
  function majRetablir(p) {
    p.li.toggleAttribute("data-vide", !p.texte.textContent.trim());
    p.retablir.hidden = p.texte.textContent.split(/\s+/).join(" ").trim() === p.texte.dataset.original;
  }

  function retablir(p) {
    const original = p.texte.dataset.original;
    if (!confirm(`Revenir au texte de la transcription d'origine ?
« ${original} »`)) return;
    p.texte.textContent = original;
    if (p === enCours) surImage.textContent = original;
    majRetablir(p);
    enregistrer(p);
  }

  function modifie(p) {
    majRetablir(p);
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

  // --- Aperçu : le lecteur bascule entre la vidéo d'origine et la vidéo doublée ---

  let sonDouble = false;

  // Change la source du lecteur en gardant la position et l'état lecture / pause.
  function changerSon(double) {
    if (double === sonDouble) return Promise.resolve();
    sonDouble = double;
    const choix = document.getElementById("choix-son");
    const t = video.currentTime, enLecture = !video.paused;
    video.src = double ? `/projets/${PROJET}/export?apercu=1&v=${choix.dataset.version}`
                       : `/projets/${PROJET}/video`;
    for (const r of document.querySelectorAll('input[name="son"]')) r.checked = (r.value === "doublee") === double;
    return new Promise((ok) => {
      video.addEventListener("loadedmetadata", () => {
        video.currentTime = t;
        if (enLecture) video.play();
        ok();
      }, { once: true });
    });
  }

  // Délégation : la section « Vidéo doublée » est remplacée à la fin de chaque génération.
  document.addEventListener("change", (e) => {
    if (e.target.name === "son") changerSon(e.target.value === "doublee");
    if (e.target.name === "sous_titres") {
      const bouton = e.target.form.querySelector("button");
      bouton.textContent = bouton.dataset.libelle + (e.target.checked ? " avec sous-titres" : "");
      document.getElementById("avertissement-sous-titres").hidden = !e.target.checked;
    }
  });

  async function ecouterOriginal(p) {
    lecteurVoix.pause();
    await changerSon(false);  // « Original » : toujours le son d'origine
    allerA(p);
    finExtrait = p.fin;
    video.play();
  }

  // --- Vitesse de la voix : automatique, ou réglée à la main (clic sur la pastille) ---

  const libelleVitesse = (v) => "×" + v.toFixed(2).replace(".", ",");

  function vitesse(p) {
    return parseFloat(p.li.dataset.vitesse || p.li.dataset.vitesseAuto || "1");
  }

  function majVitesse(p) {
    const v = vitesse(p);
    p.curseur.value = v;
    p.sortie.textContent = p.vitesseReglee.textContent = libelleVitesse(v);
  }

  // Réponse du serveur après un réglage ou une nouvelle voix : vitesse et pastille à jour.
  function majCalage(p, reponse) {
    if (!("calage" in reponse)) return;
    p.li.dataset.voix = "";
    p.li.dataset.calage = reponse.calage;
    p.li.dataset.vitesseAuto = reponse.vitesse_auto;
    p.calage.title = reponse.calage_texte;
    majVitesse(p);
  }

  async function reglerVitesse(p, valeur) {
    etatEnregistrement.textContent = "Enregistrement…";
    try {
      const r = await fetch(`/projets/${PROJET}/phrases/${p.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vitesse: valeur }),
      });
      if (!r.ok) throw new Error(r.status);
      const reponse = await r.json();
      if (reponse.vitesse === null) delete p.li.dataset.vitesse;
      else p.li.dataset.vitesse = reponse.vitesse;
      majCalage(p, reponse);
      etatEnregistrement.textContent = "Enregistré.";
      etatEnregistrement.className = "";
    } catch (e) {
      majVitesse(p);
      etatEnregistrement.textContent = "Échec de l'enregistrement, réessayez (connexion ?).";
      etatEnregistrement.className = "erreur";
    }
  }

  let voixEnCours = null;  // phrase dont la voix est en lecture

  // Lecture à la vitesse de la phrase ; le navigateur garde la hauteur de la voix.
  function ecouterVoix(p) {
    video.pause();
    voixEnCours = p;
    lecteurVoix.src = `/projets/${PROJET}/phrases/${p.id}/voix?v=${Date.now()}`;  // pas de cache
    lecteurVoix.preservesPitch = true;
    lecteurVoix.defaultPlaybackRate = lecteurVoix.playbackRate = vitesse(p);
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
      if (!r.ok) {
        const erreur = await r.json().catch(() => ({}));
        throw new Error(erreur.detail || "Échec de la génération.");
      }
      const reponse = await r.json();
      p.li.dataset.etat = reponse.etat;
      majCalage(p, reponse);
      majVoix(p);
      ecouterVoix(p);
    } catch (e) {
      p.etat.textContent = e.message;
    } finally {
      p.boutonVoix.disabled = false;
      document.documentElement.classList.remove("travail");
    }
  }

  // « Voix d'origine » : la vidéo doublée garde le son d'origine de la phrase.
  async function garderOriginal(p, case_) {
    etatEnregistrement.textContent = "Enregistrement…";
    try {
      const r = await fetch(`/projets/${PROJET}/phrases/${p.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voix_origine: case_.checked }),
      });
      if (!r.ok) throw new Error(r.status);
      p.li.toggleAttribute("data-origine", (await r.json()).voix_origine);
      etatEnregistrement.textContent = "Enregistré.";
      etatEnregistrement.className = "";
    } catch (e) {
      case_.checked = !case_.checked;
      etatEnregistrement.textContent = "Échec de l'enregistrement, réessayez (connexion ?).";
      etatEnregistrement.className = "erreur";
    }
  }

  for (const p of phrases) {
    const case_ = p.li.querySelector(".garder input");
    case_.addEventListener("change", () => garderOriginal(p, case_));
    p.boutonVoix = p.li.querySelector(".voix");
    p.etat = p.li.querySelector(".etat");
    p.calage = p.li.querySelector(".calage");
    p.retablir = p.li.querySelector(".retablir");
    p.reglage = p.li.querySelector(".reglage");
    p.curseur = p.reglage.querySelector("input");
    p.sortie = p.reglage.querySelector("output");
    p.vitesseReglee = p.li.querySelector(".vitesse-reglee");
    p.calage.addEventListener("click", () => { p.reglage.hidden = !p.reglage.hidden; });
    p.curseur.addEventListener("input", () => {
      const v = parseFloat(p.curseur.value);
      p.sortie.textContent = libelleVitesse(v);
      if (voixEnCours === p) lecteurVoix.playbackRate = v;  // s'entend pendant le réglage
    });
    p.curseur.addEventListener("change", () => reglerVitesse(p, parseFloat(p.curseur.value)));
    p.reglage.querySelector(".auto").addEventListener("click", () => reglerVitesse(p, null));
    majVoix(p);
    p.retablir.addEventListener("click", () => retablir(p));
    p.li.querySelector(".original").addEventListener("click", () => ecouterOriginal(p));
    p.boutonVoix.addEventListener("click", () => voix(p));

    p.li.addEventListener("click", (e) => {
      if (e.target.closest(".actions, .retablir, .reglage")) return;
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
    await changerSon(false);  // l'ancienne vidéo doublée vient d'être remplacée
    document.getElementById("doublage").replaceWith(page.getElementById("doublage"));
    for (const p of phrases) {
      const li = page.querySelector(`#phrases li[data-id="${p.id}"]`);
      if (!li) continue;
      p.li.dataset.etat = li.dataset.etat;
      if ("voix" in li.dataset) {
        p.li.dataset.voix = "";
        p.li.dataset.calage = li.dataset.calage;
        p.li.dataset.vitesseAuto = li.dataset.vitesseAuto;
        p.calage.title = li.querySelector(".calage").title;
        majVitesse(p);
      }
      majVoix(p);
    }
  };

  window.addEventListener("beforeunload", (e) => {
    if (phrases.some((p) => p.minuterie !== null)) e.preventDefault();  // correction pas encore envoyée
  });

  modeEdition();
  afficher();
})();
