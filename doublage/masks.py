"""Boîtes de masquage des données patients : rectangles opaques gravés dans l'image, avec un texte de
remplacement facultatif (données fictives).

Les boîtes sont enregistrées par projet dans `masques.json`. Leur position est exprimée en proportion de
l'image (0 à 1), pour ne pas dépendre de la taille d'affichage dans l'éditeur.
"""

import json
import math
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

COLOR = re.compile(r"^#[0-9a-f]{6}$")
# Police du texte de remplacement : Liberation Sans (installée dans le conteneur, mêmes proportions
# qu'Arial), sinon une police proche. Désignée par son fichier, copié dans le dossier de travail : ffmpeg
# ne dépend pas de la recherche de polices du système (qui plante avec ffmpeg pour Windows).
FONT_FILES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
FONT_COPY = "police-masques.ttf"
TEXT_MAX_LENGTH = 200
# Marge de sécurité autour de la période d'une boîte, en images : la boîte apparaît un peu avant et
# disparaît un peu après, pour qu'aucune image ne laisse voir la donnée (arrondis du navigateur, d'ffmpeg).
MARGIN_FRAMES = 1.5


class MaskError(ValueError):
    pass


@dataclass
class Mask:
    id: int
    start: float  # secondes
    end: float
    x: float  # coin haut gauche, largeur et hauteur, en proportion de l'image (0 à 1)
    y: float
    w: float
    h: float
    background: str = "#ffffff"
    text: str = ""  # texte de remplacement (vide : simple cache)
    text_color: str = "#000000"
    text_size: float = 0.7  # hauteur du texte, en proportion de la hauteur de la boîte

    def check(self) -> None:
        if not 0 <= self.start < self.end:
            raise MaskError("La fin d'une boîte doit venir après son début.")
        if not (0 <= self.x and 0 <= self.y and self.w > 0 and self.h > 0
                and self.x + self.w <= 1 + 1e-6 and self.y + self.h <= 1 + 1e-6):
            raise MaskError("Boîte en dehors de l'image.")
        if not (COLOR.match(self.background) and COLOR.match(self.text_color)):
            raise MaskError("Couleur invalide (attendu : #rrggbb).")
        if len(self.text) > TEXT_MAX_LENGTH or "\n" in self.text or "\r" in self.text:
            raise MaskError(f"Texte de remplacement : une ligne, {TEXT_MAX_LENGTH} caractères au plus.")
        if not 0.2 <= self.text_size <= 1:
            raise MaskError("Taille du texte invalide.")

    def visible_at(self, t: float, fps: float) -> bool:
        lo, hi = self.window(fps)
        return lo <= t <= hi

    def window(self, fps: float) -> tuple[float, float]:
        """Période d'affichage dans la vidéo, marge de sécurité comprise."""
        margin = MARGIN_FRAMES / fps
        return max(0.0, self.start - margin), self.end + margin

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        """Rectangle en pixels (x, y, largeur, hauteur), arrondi vers l'extérieur sur des valeurs paires
        (l'image est sous-échantillonnée par 2 en couleur) : la boîte couvre toujours au moins la zone dessinée."""
        left = max(0, math.floor(self.x * width / 2) * 2)
        top = max(0, math.floor(self.y * height / 2) * 2)
        right = min(width, math.ceil((self.x + self.w) * width / 2) * 2)
        bottom = min(height, math.ceil((self.y + self.h) * height / 2) * 2)
        return left, top, right - left, bottom - top


def masks_path(folder: Path) -> Path:
    return folder / "masques.json"


def load_masks(folder: Path) -> list[Mask]:
    path = masks_path(folder)
    if not path.exists():
        return []
    return [Mask(**m) for m in json.loads(path.read_text(encoding="utf-8"))["masks"]]


def save_masks(folder: Path, masks: list[Mask]) -> None:
    data = {"masks": [asdict(m) for m in sorted(masks, key=lambda m: (m.start, m.id))]}
    # Écriture puis remplacement : le doublage peut lire le fichier à tout moment.
    path = masks_path(folder)
    partial = path.with_suffix(".partiel")
    partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(path)


def _copy_font(folder: Path) -> None:
    source = next((Path(f) for f in FONT_FILES if Path(f).exists()), None)
    if source is None:
        raise MaskError("Aucune police disponible pour le texte de remplacement des boîtes.")
    copy = folder / FONT_COPY
    if not copy.exists() or copy.stat().st_size != source.stat().st_size:
        shutil.copyfile(source, copy)


def masks_filter(masks: list[Mask], width: int, height: int, fps: float, folder: Path,
                 at: float | None = None) -> str | None:
    """Filtres ffmpeg qui gravent les boîtes dans l'image (None : aucune boîte).

    Les textes de remplacement sont écrits dans `folder` (`masque-<id>.txt`) et désignés par leur nom :
    ffmpeg doit être lancé depuis ce dossier. Avec `at`, seules les boîtes visibles à cet instant sont
    gravées, sans condition de temps (image d'aperçu : la vidéo y est lue à partir de `at`).
    """
    filters = []
    for mask in masks:
        if at is not None and not mask.visible_at(at, fps):
            continue
        lo, hi = mask.window(fps)
        enable = "" if at is not None else f":enable='between(t,{lo:.4f},{hi:.4f})'"
        x, y, w, h = mask.pixels(width, height)
        filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x{mask.background[1:]}@1:t=fill{enable}")
        if mask.text.strip():
            textfile = folder / f"masque-{mask.id}.txt"
            textfile.write_text(mask.text.strip(), encoding="utf-8")
            size = max(6, round(mask.text_size * mask.h * height))
            _copy_font(folder)
            filters.append(
                f"drawtext=textfile={textfile.name}:expansion=none:fontfile={FONT_COPY}:fontsize={size}"
                f":fontcolor=0x{mask.text_color[1:]}:x={x + round(size * 0.25)}:y={y}+({h}-th)/2{enable}")
    return ",".join(filters) or None
