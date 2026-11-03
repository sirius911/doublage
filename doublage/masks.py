"""Boîtes de masquage des données patients : rectangles opaques gravés dans l'image, avec un texte de
remplacement facultatif (données fictives).

Les boîtes sont enregistrées par projet dans `masques.json`. Leur position est exprimée en proportion de
l'image (0 à 1), pour ne pas dépendre de la taille d'affichage dans l'éditeur.
"""

import json
import math
import re
import shutil
from dataclasses import asdict, dataclass, field
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
# Une boîte couvre les images dont l'instant (début de l'image) est dans [start, end[ : l'éditeur règle
# start et end à l'image près (start = n° de la première image / fps, end = n° de la dernière + 1 / fps).
# Marge de sécurité : une image de plus de chaque côté, pour qu'aucune image ne laisse voir la donnée
# (décalage éventuel entre le navigateur et ffmpeg). Pour la même raison, une boîte qui suit le contenu
# couvre sur chaque image sa position et celles des images voisines.
MARGIN_FRAMES = 1
MAX_KEYS = 2000


@dataclass
class Key:
    """Position d'une boîte qui suit le contenu, à un instant (calé sur une image)."""
    t: float
    x: float
    y: float
    w: float
    h: float


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
    # Suivi du contenu (défilements) : positions à quelques instants, interpolées entre elles, gardées
    # avant la première et après la dernière. Vide : boîte fixe (x, y, w, h).
    keys: list[Key] = field(default_factory=list)

    def __post_init__(self):
        self.keys = sorted((Key(**k) if isinstance(k, dict) else k for k in self.keys), key=lambda k: k.t)

    def check(self) -> None:
        if not 0 <= self.start < self.end:
            raise MaskError("La fin d'une boîte doit venir après son début.")
        if not _inside(self.x, self.y, self.w, self.h):
            raise MaskError("Boîte en dehors de l'image.")
        if not (COLOR.match(self.background) and COLOR.match(self.text_color)):
            raise MaskError("Couleur invalide (attendu : #rrggbb).")
        if len(self.text) > TEXT_MAX_LENGTH or "\n" in self.text or "\r" in self.text:
            raise MaskError(f"Texte de remplacement : une ligne, {TEXT_MAX_LENGTH} caractères au plus.")
        if not 0.2 <= self.text_size <= 1:
            raise MaskError("Taille du texte invalide.")

        if len(self.keys) > MAX_KEYS:
            raise MaskError("Trop de positions pour une boîte.")
        for k in self.keys:
            if not (k.t >= 0 and _inside(k.x, k.y, k.w, k.h)):
                raise MaskError("Position de suivi en dehors de l'image.")

    def frames(self, fps: float) -> tuple[int, int]:
        """N° de la première et de la dernière image masquées (sans la marge)."""
        return round(self.start * fps), round(self.end * fps) - 1

    def rect(self, n: int, fps: float) -> tuple[float, float, float, float]:
        """Position (x, y, w, h, en proportion) sur l'image n° n : interpolée entre les positions de suivi."""
        if not self.keys:
            return self.x, self.y, self.w, self.h
        frames = [round(k.t * fps) for k in self.keys]
        for i in range(len(frames) - 1):
            fa, fb, a, b = frames[i], frames[i + 1], self.keys[i], self.keys[i + 1]
            if n < fb:
                r = min(1.0, max(0.0, (n - fa) / (fb - fa))) if fb > fa else 1.0
                return (a.x + (b.x - a.x) * r, a.y + (b.y - a.y) * r,
                        a.w + (b.w - a.w) * r, a.h + (b.h - a.h) * r)
        k = self.keys[-1]
        return k.x, k.y, k.w, k.h

    def safe_pixels(self, n: int, fps: float, width: int, height: int) -> tuple[int, int, int, int]:
        """Rectangle gravé sur l'image n° n : positions de cette image et des images voisines réunies (un
        décalage d'une image avec le contenu ne laisse rien voir), en pixels arrondis vers l'extérieur."""
        first, last = self.frames(fps)
        rects = [pixels(*self.rect(min(last, max(first, k)), fps), width, height) for k in (n - 1, n, n + 1)]
        left, top = min(r[0] for r in rects), min(r[1] for r in rects)
        right, bottom = max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects)
        return left, top, right - left, bottom - top

    def runs(self, fps: float, width: int, height: int) -> list[tuple[int, int, tuple[int, int, int, int]]]:
        """Images masquées, marge comprise, par plages de même rectangle : (première, dernière, rectangle)."""
        first, last = self.frames(fps)
        result = []
        for n in range(max(0, first - MARGIN_FRAMES), last + MARGIN_FRAMES + 1):
            rect = self.safe_pixels(n, fps, width, height)
            if result and result[-1][2] == rect:
                result[-1] = (result[-1][0], n, rect)
            else:
                result.append((n, n, rect))
        return result

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        return pixels(self.x, self.y, self.w, self.h, width, height)


def _inside(x: float, y: float, w: float, h: float) -> bool:
    return 0 <= x and 0 <= y and w > 0 and h > 0 and x + w <= 1 + 1e-6 and y + h <= 1 + 1e-6


def pixels(x: float, y: float, w: float, h: float, width: int, height: int) -> tuple[int, int, int, int]:
    """Rectangle en pixels (x, y, largeur, hauteur), arrondi vers l'extérieur sur des valeurs paires
    (l'image est sous-échantillonnée par 2 en couleur) : la boîte couvre toujours au moins la zone dessinée."""
    left = max(0, math.floor(x * width / 2) * 2)
    top = max(0, math.floor(y * height / 2) * 2)
    right = min(width, math.ceil((x + w) * width / 2) * 2)
    bottom = min(height, math.ceil((y + h) * height / 2) * 2)
    return left, top, right - left, bottom - top


def image_at(t: float, fps: float) -> int:
    """N° de l'image affichée à l'instant t (même calcul que l'éditeur)."""
    return math.floor(t * fps + 1e-3)


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


def _between(first: int, last: int, fps: float) -> str:
    # Bornes au milieu des intervalles entre images : pas d'image en limite d'arrondi.
    return f":enable='between(t,{max(0.0, (first - 0.5) / fps):.4f},{(last + 0.5) / fps:.4f})'"


def _piecewise(times: list[float], values: list[float]) -> str:
    """Expression ffmpeg de t : interpolation linéaire entre les points (times, values), constante au-delà
    (à placer entre apostrophes dans le filtre)."""
    expr = f"{values[-1]:.1f}"
    for i in range(len(times) - 2, -1, -1):
        t0, t1, v0, v1 = times[i], times[i + 1], values[i], values[i + 1]
        slope = (v1 - v0) / (t1 - t0) if t1 > t0 else 0.0
        expr = f"if(lt(t,{t1:.4f}),{v0:.1f}+({slope:.4f})*(t-{t0:.4f}),{expr})"
    return f"if(lt(t,{times[0]:.4f}),{values[0]:.1f},{expr})"


def masks_filter(masks: list[Mask], width: int, height: int, fps: float, folder: Path,
                 at: float | None = None) -> str | None:
    """Filtres ffmpeg qui gravent les boîtes dans l'image (None : aucune boîte).

    Les textes de remplacement sont écrits dans `folder` (`masque-<id>.txt`) et désignés par leur nom :
    ffmpeg doit être lancé depuis ce dossier. Avec `at`, seules les boîtes visibles à cet instant sont
    gravées, sans condition de temps (image d'aperçu : la vidéo y est lue à partir de `at`).
    Une boîte qui suit le contenu est gravée par plages d'images de même rectangle (un drawbox par plage :
    la position d'un drawbox ne peut pas varier avec le temps).
    """
    filters = []
    shown = None if at is None else image_at(at, fps)
    for mask in masks:
        runs = mask.runs(fps, width, height)
        if shown is not None:
            runs = [(shown, shown, r) for a, b, r in runs if a <= shown <= b]
            if not runs:
                continue
        for first, last, (x, y, w, h) in runs:
            enable = "" if at is not None else _between(first, last, fps)
            filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x{mask.background[1:]}@1:t=fill{enable}")
        if mask.text.strip():
            textfile = folder / f"masque-{mask.id}.txt"
            textfile.write_text(mask.text.strip(), encoding="utf-8")
            size = max(6, round(mask.text_size * mask.rect(mask.frames(fps)[0], fps)[3] * height))
            _copy_font(folder)
            first, last = mask.frames(fps)
            if shown is not None or len(mask.keys) < 2:
                x, y, _, h = pixels(*mask.rect(first if shown is None else shown, fps), width, height)
                tx, ty = f"{x + round(size * 0.25)}", f"{y}+({h}-th)/2"
            else:  # le texte suit la boîte : position interpolée en fonction du temps
                keys = [(round(k.t * fps) / fps, pixels(k.x, k.y, k.w, k.h, width, height)) for k in mask.keys]
                times = [k[0] for k in keys]
                tx = "'" + _piecewise(times, [p[0] + round(size * 0.25) for _, p in keys]) + "'"
                ty = "'" + _piecewise(times, [p[1] + p[3] / 2 for _, p in keys]) + "-th/2'"
            enable = "" if at is not None else _between(max(0, first - MARGIN_FRAMES), last + MARGIN_FRAMES, fps)
            filters.append(
                f"drawtext=textfile={textfile.name}:expansion=none:fontfile={FONT_COPY}:fontsize={size}"
                f":fontcolor=0x{mask.text_color[1:]}:x={tx}:y={ty}{enable}")
    return ",".join(filters) or None
