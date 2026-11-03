// Masquage des données patients : boîtes opaques posées sur la vidéo, avec un texte de remplacement
// facultatif. Les boîtes sont tracées sur l'image (vidéo en pause), affichées sur le lecteur pendant leur
// période, et gravées dans l'image de la vidéo doublée par le serveur. Position en proportion de l'image.
(() => {
  const video = document.getElementById("video");
  const ecran = video.parentElement;
  const calque = document.getElementById("calque-masques");
  const liste = document.getElementById("boites");
  const boutonNouvelle = document.getElementById("nouvelle-boite");
  const boutonApercu = document.getElementById("apercu-masques");
  const aide = document.getElementById("aide-masquage");
  const apercu = document.getElementById("apercu-sous-titres");
  const statut = (texte, erreur) => window.statutEditeur(texte, erreur);
  const AIDE = aide.textContent;
  const DUREE_PAR_DEFAUT = 3;  // secondes : à ajuster avec « fin ici »

  let boites = [];  // { donnees (comme l'API), div, li }
  let choisie = null;
  let mode = null;  // null, "trace" (nouvelle boîte) ou "pipette"

  const tc = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(2).padStart(5, "0")}`;

  // --- Réglage à l'image près ---
  // Une boîte couvre les images n° premiere à derniere : debut = premiere / FPS, fin = (derniere + 1) / FPS.
  // L'image n° n est affichée de n / FPS à (n + 1) / FPS ; on s'y place en son milieu (pas d'arrondi douteux).
  const FPS = window.IMAGES_PAR_SECONDE || 30;
  const imageA = (t) => Math.floor(t * FPS + 1e-3);
  const premiere = (d) => Math.round(d.debut * FPS);
  const derniere = (d) => Math.round(d.fin * FPS) - 1;
  function allerImage(n) {
    video.pause();
    video.currentTime = Math.max(0, (n + 0.5) / FPS);
  }

  const imageAffichee = document.getElementById("image-affichee");
  const tempsImage = document.getElementById("temps-image");
  function majImageAffichee(t) {
    const n = imageA(t);
    imageAffichee.textContent = n;
    tempsImage.textContent = `(${tc(n / FPS)})`;
  }

  // Image précédente / suivante : boutons ◀ ▶ sous la vidéo, et flèches du clavier hors saisie de texte.
  // Les flèches remplacent le saut de 5 s du lecteur (écoute en phase de capture, avant le lecteur).
  const pas = (sens) => allerImage(imageA(video.currentTime) + sens);
  document.getElementById("image-precedente").addEventListener("click", () => pas(-1));
  document.getElementById("image-suivante").addEventListener("click", () => pas(1));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
    const cible = e.target;
    if (cible.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(cible.tagName)) return;
    e.preventDefault();
    e.stopPropagation();
    pas(e.key === "ArrowRight" ? 1 : -1);
  }, true);

  // --- Calque posé exactement sur l'image (la vidéo peut avoir des bandes noires dans le lecteur) ---

  function placerCalque() {
    if (!video.videoWidth) return;
    const l = video.clientWidth, h = video.clientHeight;
    const echelle = Math.min(l / video.videoWidth, h / video.videoHeight);
    const lv = video.videoWidth * echelle, hv = video.videoHeight * echelle;
    Object.assign(calque.style, {
      left: `${video.offsetLeft + (l - lv) / 2}px`, top: `${video.offsetTop + (h - hv) / 2}px`,
      width: `${lv}px`, height: `${hv}px`,
    });
    for (const b of boites) dessiner(b);
  }
  new ResizeObserver(placerCalque).observe(video);
  video.addEventListener("loadedmetadata", placerCalque);

  // Position du pointeur en proportion de l'image (0 à 1).
  function proportion(e) {
    const r = calque.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  }

  // --- Couleurs prises sur l'image (la vidéo est servie par l'application : lecture des pixels permise) ---

  const toile = document.createElement("canvas");
  function imageCourante() {
    toile.width = video.videoWidth;
    toile.height = video.videoHeight;
    const ctx = toile.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(video, 0, 0);
    return ctx;
  }
  const hex = (r, g, b) => "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");

  function couleurA(ctx, x, y) {
    const px = Math.min(toile.width - 1, Math.round(x * toile.width));
    const py = Math.min(toile.height - 1, Math.round(y * toile.height));
    const [r, g, b] = ctx.getImageData(px, py, 1, 1).data;
    return hex(r, g, b);
  }

  // Couleur de fond d'une zone : la plus fréquente sur son pourtour (la donnée est au milieu).
  function fondDe(d) {
    const ctx = imageCourante(), compte = new Map();
    for (let i = 0; i <= 20; i++) {
      const f = i / 20;
      for (const [x, y] of [[d.x + f * d.largeur, d.y], [d.x + f * d.largeur, d.y + d.hauteur],
                            [d.x, d.y + f * d.hauteur], [d.x + d.largeur, d.y + f * d.hauteur]]) {
        const c = couleurA(ctx, x, y);
        compte.set(c, (compte.get(c) || 0) + 1);
      }
    }
    return [...compte].sort((a, b) => b[1] - a[1])[0][0];
  }

  // Texte noir sur fond clair, blanc sur fond foncé.
  function texteLisible(fond) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(fond.slice(i, i + 2), 16));
    return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "#000000" : "#ffffff";
  }

  // --- Affichage des boîtes sur le lecteur ---

  // --- Suivi du contenu (défilements) : positions à quelques images, interpolées entre elles (comme à
  // l'export, masks.py), gardées avant la première et après la dernière. ---

  const imagePosition = (p) => Math.round(p.t * FPS);
  function rectA(d, n) {
    const ps = d.positions || [];
    if (!ps.length) return { x: d.x, y: d.y, largeur: d.largeur, hauteur: d.hauteur };
    for (let i = 0; i < ps.length - 1; i++) {
      const fa = imagePosition(ps[i]), fb = imagePosition(ps[i + 1]), a = ps[i], b = ps[i + 1];
      if (n < fb) {
        const r = fb > fa ? Math.min(1, Math.max(0, (n - fa) / (fb - fa))) : 1;
        const m = (k) => a[k] + (b[k] - a[k]) * r;
        return { x: m("x"), y: m("y"), largeur: m("largeur"), hauteur: m("hauteur") };
      }
    }
    const { x, y, largeur, hauteur } = ps[ps.length - 1];
    return { x, y, largeur, hauteur };
  }
  // Positions avec celle de l'image n remplacée ou ajoutée ; la boîte fixe garde la première.
  function avecPosition(d, n, r) {
    const ps = (d.positions || []).filter((p) => imagePosition(p) !== n);
    ps.push({ t: n / FPS, ...r });
    ps.sort((a, b) => a.t - b.t);
    return { positions: ps, ...premierePosition(ps) };
  }
  const premierePosition = (ps) => ({ x: ps[0].x, y: ps[0].y, largeur: ps[0].largeur, hauteur: ps[0].hauteur });

  let imageVue = 0;  // n° de l'image sur laquelle les boîtes sont placées

  function placer(b, r = rectA(b.donnees, imageVue)) {
    Object.assign(b.div.style, {
      left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.largeur * 100}%`, height: `${r.hauteur * 100}%`,
    });
    const taille = b.donnees.taille_texte * r.hauteur * calque.clientHeight;
    Object.assign(b.texte.style, { fontSize: `${taille}px`, paddingLeft: `${taille * 0.25}px` });
  }

  function dessiner(b) {
    const d = b.donnees;
    Object.assign(b.div.style, { background: d.fond, color: d.couleur_texte });
    b.texte.textContent = d.texte;
    b.div.classList.toggle("suivie", !!(d.positions || []).length);
    placer(b);
  }

  // Sur la vidéo doublée (aperçu « nouvelle voix »), les boîtes sont déjà gravées : on montre l'image réelle,
  // avec seulement le contour des boîtes (vérification : la donnée ne doit pas dépasser du cadre).
  const surVideoDoublee = () => video.currentSrc.includes("/export");
  const contours = document.getElementById("contours-boites");
  contours.addEventListener("change", () => afficher());

  // `t` : instant de l'image affichée (donné par le navigateur pendant la lecture, plus juste que currentTime).
  function afficher(t = video.currentTime) {
    const n = imageA(t), doublee = surVideoDoublee();
    calque.classList.toggle("en-pause", video.paused);  // boîtes sélectionnables à l'arrêt seulement
    calque.classList.toggle("verification", doublee);
    contours.parentElement.hidden = !doublee || !boites.length;
    majImageAffichee(t);
    imageVue = n;
    for (const b of boites) {
      const visible = (!doublee || contours.checked) && premiere(b.donnees) <= n && n <= derniere(b.donnees);
      b.div.hidden = !visible;
      b.div.classList.toggle("choisie", b === choisie);
      if (visible) placer(b);
      majPositions(b);
    }
  }

  function suivre(_maintenant, image) {
    afficher(image ? image.mediaTime : video.currentTime);
    if (!video.paused) {
      if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(suivre);
      else requestAnimationFrame(() => suivre());
    }
  }
  video.addEventListener("play", () => { annulerMode(); suivre(); });
  for (const evt of ["seeked", "pause", "loadeddata"]) video.addEventListener(evt, () => afficher());
  video.addEventListener("timeupdate", () => { if (video.paused) afficher(); });

  // --- Enregistrement ---

  async function envoyer(methode, url, donnees) {
    statut("Enregistrement…");
    const r = await fetch(url, {
      method: methode, headers: { "Content-Type": "application/json" },
      body: donnees ? JSON.stringify(donnees) : undefined,
    });
    if (!r.ok) {
      const erreur = await r.json().catch(() => ({}));
      const message = typeof erreur.detail === "string" ? erreur.detail : "Échec de l'enregistrement.";
      statut(message, true);
      throw new Error(message);
    }
    statut("Enregistré.");
    signalerVideoPerimee();
    return r.status === 204 ? null : r.json();
  }

  async function modifier(b, changements) {
    const avant = b.donnees;
    b.donnees = { ...avant, ...changements };
    dessiner(b); majLigne(b); afficher();
    try {
      b.donnees = await envoyer("PUT", `/projets/${PROJET}/masques/${avant.id}`, b.donnees);
    } catch {
      b.donnees = avant;
    }
    dessiner(b); majLigne(b); afficher();
    trier();
  }

  // La vidéo doublée déjà générée ne contient pas cette modification : à signaler tout de suite.
  function signalerVideoPerimee() {
    const lien = document.querySelector('#doublage a[href$="/export"]');
    if (!lien || document.querySelector("#doublage .masquage-perime")) return;
    const p = document.createElement("p");
    p.className = "masquage-perime";
    p.innerHTML = "<strong>Les boîtes de masquage ont changé depuis : cette vidéo ne les contient pas. "
      + "Mettez-la à jour avant de la diffuser.</strong>";
    lien.closest("p").after(p);
  }

  // --- Liste des boîtes ---

  function ligne(b) {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="periode">
      <span class="borne">Début <button type="button" class="aller-debut" title="Aller à la première image masquée"></button>
      <button type="button" class="moins-debut" title="Commencer une image plus tôt">−</button><button type="button"
       class="plus-debut" title="Commencer une image plus tard">+</button>
      <button type="button" class="debut-ici" title="Commencer à l'image affichée">ici</button></span>
      <span class="borne">Fin <button type="button" class="aller-fin" title="Aller à la dernière image masquée"></button>
      <button type="button" class="moins-fin" title="Finir une image plus tôt">−</button><button type="button"
       class="plus-fin" title="Finir une image plus tard">+</button>
      <button type="button" class="fin-ici" title="Finir à l'image affichée (incluse)">ici</button></span></span>
      <span class="reglages">
      <label title="Couleur de fond">Fond <input type="color" class="fond"></label>
      <button type="button" class="pipette" title="Prendre la couleur de fond sur l'image">pipette</button>
      <input type="text" class="texte" maxlength="200" placeholder="Texte de remplacement (facultatif, fictif)">
      <label title="Couleur du texte"><input type="color" class="couleur-texte"></label>
      <label title="Taille du texte">A<input type="range" class="taille" min="0.3" max="1" step="0.05"></label>
      <button type="button" class="supprimer" title="Supprimer la boîte">✕</button></span>
      <span class="suivi-ligne">
      <label title="La boîte suit la donnée quand l'écran défile"><input type="checkbox" class="suivi"> suivre le contenu</label>
      <span class="positions" hidden><button type="button" class="pos-prec" title="Aller à la position précédente">◀</button>
      <span class="nb-positions"></span>
      <button type="button" class="pos-suiv" title="Aller à la position suivante">▶</button>
      <button type="button" class="pos-suppr" title="Supprimer la position de l'image affichée">✕ position ici</button></span></span>`;
    const q = (s) => li.querySelector(s);
    // Première et dernière image masquées ; après un réglage, la vidéo montre l'image concernée.
    const regler = (debutImage, finImage, voir) => {
      choisir(b);
      if (finImage < debutImage) { statut("La fin de la boîte doit venir après son début.", true); return; }
      if (debutImage < 0) { statut("La boîte commence déjà à la première image.", true); return; }
      modifier(b, { debut: debutImage / FPS, fin: (finImage + 1) / FPS });
      allerImage(voir);
    };
    const d = () => b.donnees;
    q(".aller-debut").addEventListener("click", () => { choisir(b); allerImage(premiere(d())); });
    q(".aller-fin").addEventListener("click", () => { choisir(b); allerImage(derniere(d())); });
    q(".moins-debut").addEventListener("click", () => regler(premiere(d()) - 1, derniere(d()), premiere(d()) - 1));
    q(".plus-debut").addEventListener("click", () => regler(premiere(d()) + 1, derniere(d()), premiere(d()) + 1));
    q(".moins-fin").addEventListener("click", () => regler(premiere(d()), derniere(d()) - 1, derniere(d()) - 1));
    q(".plus-fin").addEventListener("click", () => regler(premiere(d()), derniere(d()) + 1, derniere(d()) + 1));
    q(".debut-ici").addEventListener("click", () => { const n = imageA(video.currentTime); regler(n, derniere(d()), n); });
    q(".fin-ici").addEventListener("click", () => { const n = imageA(video.currentTime); regler(premiere(d()), n, n); });
    q(".fond").addEventListener("change", (e) => modifier(b, { fond: e.target.value }));
    q(".couleur-texte").addEventListener("change", (e) => modifier(b, { couleur_texte: e.target.value }));
    q(".taille").addEventListener("change", (e) => modifier(b, { taille_texte: parseFloat(e.target.value) }));
    q(".taille").addEventListener("input", (e) => { b.donnees.taille_texte = parseFloat(e.target.value); dessiner(b); });
    q(".texte").addEventListener("input", (e) => { b.donnees.texte = e.target.value; dessiner(b); });
    q(".texte").addEventListener("change", (e) => modifier(b, { texte: e.target.value }));
    q(".texte").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
    q(".pipette").addEventListener("click", () => {
      choisir(b);
      video.pause();
      changerMode("pipette", "Cliquez sur l'image à l'endroit dont la boîte doit prendre la couleur (Échap : annuler).");
    });
    q(".supprimer").addEventListener("click", async () => {
      if (!confirm("Supprimer cette boîte de masquage ?")) return;
      try {
        await envoyer("DELETE", `/projets/${PROJET}/masques/${b.donnees.id}`);
      } catch { return; }
      b.div.remove(); li.remove();
      boites = boites.filter((x) => x !== b);
      if (choisie === b) choisir(null);
      majNombre();
    });
    // Suivi : la première position est prise sur l'image affichée (ou au début de la boîte si elle n'y est
    // pas) ; ensuite, chaque déplacement de la boîte sur une autre image ajoute une position.
    q(".suivi").addEventListener("change", (e) => {
      const coche = e.target.checked;
      choisir(b);  // remet la case selon les données : on a lu son état avant
      const ps = d().positions || [];
      if (coche) {
        let n = imageA(video.currentTime);
        if (n < premiere(d()) || n > derniere(d())) n = premiere(d());
        modifier(b, avecPosition(d(), n, rectA(d(), n)));
        statut("Suivi activé : sur une autre image, déplacez la boîte sur la donnée ; chaque déplacement "
          + "ajoute une position, la boîte glisse de l'une à l'autre.");
      } else {
        if (ps.length > 1 && !confirm(`Ne plus suivre le contenu ? Les ${ps.length} positions seront effacées `
          + "(la boîte reste à sa position sur l'image affichée).")) return;
        modifier(b, { positions: [], ...rectA(d(), imageA(video.currentTime)) });
      }
    });
    const allerPosition = (sens) => {
      choisir(b);
      const n = imageA(video.currentTime), images = (d().positions || []).map(imagePosition);
      const cible = sens < 0 ? images.filter((i) => i < n).pop() : images.find((i) => i > n);
      if (cible === undefined) statut(sens < 0 ? "Pas de position avant cette image." : "Pas de position après cette image.");
      else allerImage(cible);
    };
    q(".pos-prec").addEventListener("click", () => allerPosition(-1));
    q(".pos-suiv").addEventListener("click", () => allerPosition(1));
    q(".pos-suppr").addEventListener("click", () => {
      choisir(b);
      const n = imageA(video.currentTime), ps = d().positions || [];
      const reste = ps.filter((p) => imagePosition(p) !== n);
      if (reste.length === ps.length) { statut("Aucune position sur cette image.", true); return; }
      if (!reste.length) { statut("C'est la dernière position : décochez « suivre le contenu ».", true); return; }
      modifier(b, { positions: reste, ...premierePosition(reste) });
    });
    li.addEventListener("click", (e) => { if (!e.target.closest("button, input, label")) choisir(b); });
    return li;
  }

  function majPositions(b) {
    const q = (s) => b.li.querySelector(s), ps = b.donnees.positions || [];
    const images = ps.map(imagePosition), i = images.indexOf(imageVue);
    q(".suivi").checked = ps.length > 0;
    q(".positions").hidden = !ps.length;
    q(".nb-positions").textContent = `${ps.length} position${ps.length > 1 ? "s" : ""}`
      + (i >= 0 ? ` (n° ${i + 1} sur cette image)` : "");
    b.div.classList.toggle("sur-position", i >= 0);
  }

  function majLigne(b) {
    const q = (s) => b.li.querySelector(s), d = b.donnees;
    q(".aller-debut").textContent = `${tc(d.debut)} (n° ${premiere(d)})`;
    q(".aller-fin").textContent = `${tc(derniere(d) / FPS)} (n° ${derniere(d)})`;
    q(".fond").value = d.fond;
    q(".couleur-texte").value = d.couleur_texte;
    q(".taille").value = d.taille_texte;
    if (document.activeElement !== q(".texte")) q(".texte").value = d.texte;
  }

  function trier() {
    boites.sort((a, b) => a.donnees.debut - b.donnees.debut || a.donnees.id - b.donnees.id);
    for (const b of boites) liste.append(b.li);
  }

  function majNombre() {
    document.getElementById("nombre-boites").textContent = boites.length ? `(${boites.length})` : "";
    boutonApercu.hidden = !boites.length;
  }

  function choisir(b) {
    choisie = b;
    for (const x of boites) x.li.classList.toggle("choisie", x === b);
    if (b) b.li.scrollIntoView({ block: "nearest" });
    afficher();
  }

  function ajouter(donnees) {
    const div = document.createElement("div");
    div.className = "masque";
    div.innerHTML = '<span class="texte-masque"></span><span class="poignee" title="Redimensionner"></span>';
    const b = { donnees, div, texte: div.querySelector(".texte-masque") };
    b.li = ligne(b);
    calque.append(div);
    boites.push(b);
    deplacable(b);
    dessiner(b); majLigne(b);
    return b;
  }

  // --- Déplacer et redimensionner la boîte choisie (vidéo en pause) ---

  function deplacable(b) {
    b.div.addEventListener("pointerdown", (e) => {
      if (mode || !video.paused) return;
      e.preventDefault(); e.stopPropagation();
      if (choisie !== b) { choisir(b); return; }
      const poignee = e.target.classList.contains("poignee");
      // Boîte suivie : on déplace sa position sur l'image affichée (ajoutée si elle n'existe pas).
      const n = imageVue, depart = proportion(e), avant = rectA(b.donnees, n), r = { ...avant };
      b.div.setPointerCapture(e.pointerId);
      const bouger = (m) => {
        const p = proportion(m), dx = p.x - depart.x, dy = p.y - depart.y;
        if (poignee) {
          r.largeur = Math.max(0.005, Math.min(1 - avant.x, avant.largeur + dx));
          r.hauteur = Math.max(0.005, Math.min(1 - avant.y, avant.hauteur + dy));
        } else {
          r.x = Math.max(0, Math.min(1 - avant.largeur, avant.x + dx));
          r.y = Math.max(0, Math.min(1 - avant.hauteur, avant.y + dy));
        }
        placer(b, r);
      };
      const finir = () => {
        b.div.removeEventListener("pointermove", bouger);
        if (["x", "y", "largeur", "hauteur"].every((k) => r[k] === avant[k])) { placer(b); return; }
        modifier(b, (b.donnees.positions || []).length ? avecPosition(b.donnees, n, r) : r);
      };
      b.div.addEventListener("pointermove", bouger);
      b.div.addEventListener("lostpointercapture", finir, { once: true });
    });
  }

  // --- Tracer une nouvelle boîte, prendre une couleur ---

  function changerMode(nouveau, message) {
    mode = nouveau;
    calque.classList.toggle("trace", mode !== null);
    aide.textContent = message || AIDE;
    aide.classList.toggle("actif", mode !== null);
  }
  function annulerMode() { changerMode(null); }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mode) annulerMode(); });

  boutonNouvelle.addEventListener("click", () => {
    video.pause();
    choisir(null);
    changerMode("trace", "Tracez un rectangle sur l'image, autour de la donnée à cacher (Échap : annuler).");
  });

  calque.addEventListener("pointerdown", (e) => {
    if (!mode) return;
    e.preventDefault();
    const depart = proportion(e);
    if (mode === "pipette") {
      const couleur = couleurA(imageCourante(), depart.x, depart.y);
      annulerMode();
      if (choisie) modifier(choisie, { fond: couleur, couleur_texte: texteLisible(couleur) });
      return;
    }
    const cadre = document.createElement("div");
    cadre.className = "trace-en-cours";
    calque.append(cadre);
    calque.setPointerCapture(e.pointerId);
    let zone = null;
    const bouger = (m) => {
      const p = proportion(m);
      zone = { x: Math.min(p.x, depart.x), y: Math.min(p.y, depart.y),
               largeur: Math.abs(p.x - depart.x), hauteur: Math.abs(p.y - depart.y) };
      Object.assign(cadre.style, { left: `${zone.x * 100}%`, top: `${zone.y * 100}%`,
                                   width: `${zone.largeur * 100}%`, height: `${zone.hauteur * 100}%` });
    };
    calque.addEventListener("pointermove", bouger);
    calque.addEventListener("lostpointercapture", async () => {
      calque.removeEventListener("pointermove", bouger);
      cadre.remove();
      annulerMode();
      if (!zone || zone.largeur < 0.005 || zone.hauteur < 0.005) return;  // simple clic : rien
      const fond = fondDe(zone);
      const n = imageA(video.currentTime);
      const derniereImage = video.duration ? Math.floor(video.duration * FPS) - 1 : Infinity;
      const debut = n / FPS, fin = (Math.max(n, Math.min(n + DUREE_PAR_DEFAUT * FPS - 1, derniereImage)) + 1) / FPS;
      try {
        const donnees = await envoyer("POST", `/projets/${PROJET}/masques`, {
          debut, fin, ...zone, fond, couleur_texte: texteLisible(fond), texte: "", taille_texte: 0.7,
        });
        const b = ajouter(donnees);
        trier(); majNombre(); choisir(b);
        statut(`Boîte créée pour ${DUREE_PAR_DEFAUT} s : réglez sa fin (« ici », − / +).`);
        b.li.querySelector(".texte").focus();
      } catch { /* message déjà affiché */ }
    }, { once: true });
  });

  // --- Aperçu exact : image rendue par le serveur avec les boîtes gravées (comme dans la vidéo doublée) ---

  boutonApercu.addEventListener("click", async () => {
    video.pause();
    statut("Préparation de l'aperçu…");
    const r = await fetch(`/projets/${PROJET}/sous-titres/apercu?t=${video.currentTime.toFixed(3)}&sous_titres=false`);
    if (!r.ok) { statut("Aperçu impossible.", true); return; }
    if (apercu.src) URL.revokeObjectURL(apercu.src);
    apercu.src = URL.createObjectURL(await r.blob());
    apercu.hidden = false;
    statut("Aperçu exact : cliquez sur l'image pour revenir à la vidéo.");
  });

  // --- Chargement ---

  (async () => {
    const r = await fetch(`/projets/${PROJET}/masques`);
    if (!r.ok) return;
    for (const d of (await r.json()).masques) ajouter(d);
    trier(); majNombre(); placerCalque(); afficher();
  })();
})();
