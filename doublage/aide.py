"""Page d'aide : explications courtes, illustrées par des reproductions simplifiées de l'interface
(mêmes couleurs et mêmes libellés que les vraies pages, pas de captures d'écran)."""

from .voices import SAMPLE_MAX_SECONDS, SAMPLE_MIN_SECONDS


def help_content(max_speed: float) -> str:
    speed = round((max_speed - 1) * 100)
    acceleration = (f"légèrement accélérée (jusqu'à {speed} %, sans changer la hauteur de la voix)"
                    if speed > 0 else "décalée")
    return f"""<link rel="stylesheet" href="/static/aide.css">
<div class="aide">
<h1>Aide</h1>
<p class="chapeau">Doublage remplace la voix d'un tutoriel vidéo par une voix de synthèse claire, à partir
du texte que vous relisez. La voix reste calée sur l'image. Tout se passe sur les serveurs de l'hôpital.</p>

<nav class="sommaire">
<a href="#etapes">Les 4 étapes</a><a href="#depot">Déposer une vidéo</a><a href="#editeur">Corriger le texte</a>
<a href="#pastilles">Les pastilles</a><a href="#doublee">Vidéo doublée</a><a href="#voix">Les voix</a>
<a href="#astuces">Astuces</a>
</nav>

<section id="etapes">
<h2>Les 4 étapes</h2>
<ol class="etapes">
<li><span class="num">1</span><b>Déposer</b> la vidéo du tutoriel.</li>
<li><span class="num">2</span><b>Transcrire</b> : la parole devient une liste de phrases, chacune à son moment.</li>
<li><span class="num">3</span><b>Corriger et écouter</b> les phrases, la vidéo en fond.</li>
<li><span class="num">4</span><b>Générer</b> la vidéo doublée et la <b>télécharger</b>.</li>
</ol>
</section>

<section id="depot">
<h2>Déposer une vidéo</h2>
<p>Sur la page d'accueil (« Doublage » en haut à gauche), choisissez le fichier vidéo (MP4, MKV, MOV…) et
cliquez sur <span class="bouton">Déposer la vidéo</span>. Une barre indique l'avancement de l'envoi.</p>
<p>Sur la page du projet, cliquez sur <span class="bouton">Lancer la transcription</span>. Comptez de quelques
secondes à quelques minutes selon la durée de la vidéo ; la page s'actualise toute seule à la fin.</p>
<p class="note">Les projets sont visibles par tous les utilisateurs. La croix <span class="croix">×</span> à
droite d'un projet le supprime entièrement (vidéo, texte, voix), après confirmation.</p>
</section>

<section id="editeur">
<h2>Corriger le texte</h2>
<p>Après la transcription, la page du projet devient l'éditeur : la vidéo à gauche, la liste des phrases à
droite.</p>

<figure class="schema">
<div class="mini-editeur">
  <div class="mini-gauche">
    <div class="mini-ecran">
      <span class="repere r1">1</span>
      <div class="mini-texte">Cliquez sur le bouton Enregistrer.</div>
    </div>
    <div class="mini-ligne"><span class="repere r4">4</span>Voix : <span class="mini-select">Estelle ▾</span></div>
    <div class="mini-ligne"><span class="repere r5">5</span><b>Vidéo doublée</b></div>
  </div>
  <div class="mini-phrases">
    <b>Phrases</b>
    <div class="mini-phrase"><span class="tc">00:00</span><span>Bonjour à tous.</span>
      <span class="mini-actions"><span class="bouton">▶ Original</span><span class="bouton">▶ Voix</span>
      <span class="pastille vert">●</span> <small>voix à jour</small></span></div>
    <div class="mini-phrase en-cours"><span class="tc"><span class="repere r2">2</span>00:04</span>
      <span>Cliquez sur le bouton Enregistrer.</span>
      <span class="mini-actions"><span class="repere r3">3</span><span class="bouton">▶ Original</span>
      <span class="bouton">▶ Voix</span></span></div>
    <div class="mini-phrase"><span class="tc">00:09</span><span>La fenêtre se ferme.</span>
      <span class="mini-actions"><span class="bouton">▶ Original</span><span class="bouton">▶ Voix</span></span></div>
  </div>
</div>
</figure>

<ol class="legende">
<li><span class="repere">1</span><b>Texte sur l'image.</b> La phrase en cours s'affiche sur la vidéo, comme un
sous-titre. Mettez la vidéo en <b>pause</b> : le texte est encadré en pointillés, cliquez dedans pour le
corriger.</li>
<li><span class="repere">2</span><b>Liste des phrases.</b> On peut aussi corriger le texte directement dans la
liste. Cliquer sur une phrase place la vidéo à ce moment ; la phrase en cours est surlignée en jaune et la
liste la suit pendant la lecture.</li>
<li><span class="repere">3</span><b>Écouter.</b> <span class="bouton">▶ Original</span> rejoue la phrase
d'origine ; <span class="bouton">▶ Voix</span> fait entendre la voix de synthèse (créée en quelques secondes la
première fois).</li>
<li><span class="repere">4</span><b>Voix du projet</b> : voir <a href="#voix">Les voix</a>.</li>
<li><span class="repere">5</span><b>Vidéo doublée</b> : voir <a href="#doublee">plus bas</a>.</li>
</ol>
<p class="note">Les corrections sont <b>enregistrées automatiquement</b> (« Enregistré. » s'affiche sous la
vidéo). Survolez une phrase pour voir son texte d'origine.</p>
</section>

<section id="pastilles">
<h2>Les pastilles : la voix tient-elle dans le temps ?</h2>
<p>Dès qu'une phrase a sa voix de synthèse, une pastille indique si cette voix tient dans le temps de la
phrase d'origine, pour rester calée sur l'image. Survolez-la pour le détail.</p>
<table class="pastilles">
<tr><td><span class="pastille vert">●</span></td><td><b>Ça tient.</b> Rien à faire.</td></tr>
<tr><td><span class="pastille orange">●</span></td><td><b>Corrigé automatiquement.</b> La voix déborde un peu sur
le silence qui suit, ou elle est {acceleration}. En général, rien à faire.</td></tr>
<tr><td><span class="pastille rouge">●</span></td><td><b>Trop longue.</b> Même corrigée, elle empiète sur la
phrase suivante, qui sera décalée. <b>Raccourcissez le texte</b>, puis réécoutez.</td></tr>
<tr><td><span class="pastille vert pale">●</span></td><td><b>Pastille pâle</b> : le texte a changé depuis la
voix (« texte modifié : voix à régénérer »). Cliquez sur <span class="bouton">▶ Voix</span> pour la refaire.</td></tr>
</table>
</section>

<section id="doublee">
<h2>Générer et télécharger la vidéo doublée</h2>
<figure class="schema">
<div class="mini-doublee">
  <div>Son de la vidéo : <label><input type="radio" disabled checked> original</label>
  <label><input type="radio" disabled> nouvelle voix (aperçu)</label></div>
  <div class="mini-generer"><span class="bouton">Mettre à jour la vidéo doublée</span>
  <label><input type="checkbox" disabled> Sous-titres incrustés</label></div>
  <div><span class="lien">Télécharger la vidéo doublée</span> <small>(générée le 28/10/2026 à 10:15)</small><br>
  <small>Aussi : <span class="lien">voix seule (WAV)</span>, sous-titres <span class="lien">SRT</span> /
  <span class="lien">VTT</span></small></div>
</div>
</figure>
<ul>
<li><span class="bouton">Générer la vidéo doublée</span> crée la voix des phrases qui n'en ont pas encore
(les voix déjà écoutées sont reprises telles quelles), puis assemble la vidéo. Vous pouvez continuer à corriger
pendant ce temps.</li>
<li><b>Aperçu</b> : « nouvelle voix » fait jouer la vidéo doublée dans l'éditeur, avec le texte et la liste
toujours synchronisés.</li>
<li><b>Sous-titres incrustés</b> : le texte corrigé est gravé dans l'image. Toute l'image doit alors être
recalculée : comptez en plus environ un quart de la durée de la vidéo.</li>
<li>Après une correction, un message orange le signale : cliquez sur <span class="bouton">Mettre à jour la
vidéo doublée</span> pour en tenir compte.</li>
<li>Également disponibles : la <b>voix seule</b> (fichier WAV) et les <b>sous-titres</b> (SRT ou VTT, pour les
lecteurs vidéo et les plateformes de diffusion).</li>
</ul>
</section>

<section id="voix">
<h2>Les voix</h2>
<p><b>Choisir la voix d'un projet</b> : liste « Voix » sous la vidéo de l'éditeur. Changer de voix efface les
voix déjà générées pour ce projet (le texte corrigé est conservé) ; une confirmation est demandée.</p>
<p><b>Ajouter une voix</b> : menu « Voix » en haut de la page. Il faut un enregistrement de
{SAMPLE_MIN_SECONDS} à {SAMPLE_MAX_SECONDS} secondes d'une seule personne qui parle naturellement, sans musique
ni bruit de fond (fichier audio ou vidéo). La qualité de l'enregistrement (écho, souffle) se retrouve dans la
voix produite.</p>
<p class="note attention">L'<b>accord de la personne enregistrée</b> est obligatoire. Une voix utilisée par un
projet ne peut pas être supprimée.</p>
</section>

<section id="astuces">
<h2>Astuces</h2>
<ul>
<li><b>Un mot, un sigle ou un nom mal prononcé</b> : essayez de l'écrire comme il se prononce, puis
réécoutez avec <span class="bouton">▶ Voix</span>.</li>
<li><b>Ponctuation</b> : une virgule ou un point donne en général une petite pause dans la voix.</li>
<li><b>Phrase rouge</b> : supprimez les mots inutiles (« alors », « donc », « voilà »…) ; à l'écrit, le
commentaire peut être plus court qu'à l'oral.</li>
<li>La transcription n'est jamais relancée sur un projet : vos corrections ne risquent rien.</li>
</ul>
</section>
</div>"""
