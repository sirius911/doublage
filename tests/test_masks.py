from pathlib import Path

import pytest

from doublage.masks import Mask, MaskError, load_masks, masks_filter, save_masks


def boite(**champs) -> Mask:
    return Mask(**{"id": 1, "start": 2.0, "end": 4.0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.05, **champs})


def test_enregistrement_trie_par_debut(tmp_path):
    assert load_masks(tmp_path) == []
    save_masks(tmp_path, [boite(id=1, start=5.0, end=6.0), boite(id=2, text="DUPONT Jean")])
    masques = load_masks(tmp_path)
    assert [m.id for m in masques] == [2, 1] and masques[0].text == "DUPONT Jean"


@pytest.mark.parametrize("champs", [
    {"start": 4.0, "end": 2.0}, {"x": 0.9}, {"w": 0}, {"background": "rouge"},
    {"text_color": "#FFF"}, {"text": "deux\nlignes"}, {"text": "x" * 201}, {"text_size": 3},
])
def test_boite_invalide(champs):
    with pytest.raises(MaskError):
        boite(**champs).check()


def test_rectangle_arrondi_vers_l_exterieur():
    # 0,1 × 1919 = 191,9 → 190 ; (0,1 + 0,3) × 1919 = 767,6 → 768 : la zone dessinée est couverte.
    assert boite().pixels(1919, 1080) == (190, 216, 578, 54)
    assert boite(x=0.9, w=0.1, y=0.0, h=1.0).pixels(1920, 1080) == (1728, 0, 192, 1080)


def test_marge_d_une_image_de_chaque_cote():
    # Images de 2 s à 4 s exclu (n° 60 à 119 à 30 i/s) ; avec la marge, n° 59 à 120, d'un seul tenant.
    assert boite().frames(30) == (60, 119)
    assert boite().runs(30, 1920, 1080) == [(59, 120, (192, 216, 576, 54))]
    assert boite(start=0.0).runs(30, 1920, 1080)[0][0] == 0


def suivie(**champs) -> Mask:
    # Défilement vers le haut : de y = 0,5 à 2 s (image 60) à y = 0,2 à 3 s (image 90), largeur doublée.
    return boite(start=1.0, end=4.0, keys=[{"t": 3.0, "x": 0.1, "y": 0.2, "w": 0.6, "h": 0.05},
                                           {"t": 2.0, "x": 0.1, "y": 0.5, "w": 0.3, "h": 0.05}], **champs)


def test_suivi_interpole_entre_les_positions(tmp_path):
    m = suivie()
    assert [k.t for k in m.keys] == [2.0, 3.0]  # triées
    assert m.rect(40, 30) == (0.1, 0.5, 0.3, 0.05)  # avant la première position : gardée
    assert m.rect(75, 30) == pytest.approx((0.1, 0.35, 0.45, 0.05))
    assert m.rect(110, 30) == (0.1, 0.2, 0.6, 0.05)  # après la dernière
    save_masks(tmp_path, [m])
    assert load_masks(tmp_path) == [m]
    with pytest.raises(MaskError):
        boite(keys=[{"t": 2.0, "x": 0.9, "y": 0.1, "w": 0.3, "h": 0.1}]).check()


def test_suivi_couvre_les_images_voisines():
    m = suivie()
    # Image 75 : réunion des positions des images 74, 75 et 76 (le contenu peut être décalé d'une image).
    haut = m.safe_pixels(75, 30, 1000, 1000)
    assert 338 <= haut[1] <= 340 and 410 <= haut[1] + haut[3] <= 412 and haut[0] + haut[2] >= 560
    runs = m.runs(30, 1000, 1000)
    assert runs[0][:2] == (29, 59) and runs[-1][:2] == (91, 120)  # immobile avant et après
    assert all(b + 1 == a for (_, b, _), (a, _, _) in zip(runs, runs[1:]))  # aucune image oubliée


def test_filtre_d_une_boite_suivie(tmp_path):
    filtre = masks_filter([suivie(text="DUPONT Jean")], 1000, 1000, 30, tmp_path)
    assert filtre.count("drawbox") == len(suivie().runs(30, 1000, 1000))
    texte = filtre.split("drawtext", 1)[1]
    assert "x='if(lt(t,2.0000)," in texte and "-th/2'" in texte
    apercu = masks_filter([suivie()], 1000, 1000, 30, tmp_path, at=2.5)
    assert apercu.count("drawbox") == 1 and "enable" not in apercu


def test_filtre_ffmpeg(tmp_path):
    assert masks_filter([], 1920, 1080, 30, tmp_path) is None
    filtre = masks_filter([boite(), boite(id=2, text=" DUPONT Jean ", background="#eeeeee")],
                          1920, 1080, 30, tmp_path)
    cache, fond, texte = filtre.split(",drawbox", 1)[0], *filtre.split(",drawbox", 1)[1].split(",drawtext")
    assert cache == "drawbox=x=192:y=216:w=576:h=54:color=0xffffff@1:t=fill:enable='between(t,1.9500,4.0167)'"
    assert "color=0xeeeeee@1" in fond
    assert "textfile=masque-2.txt" in texte and "expansion=none" in texte and "fontsize=38" in texte
    assert texte.endswith(":enable='between(t,1.9500,4.0167)'")
    assert (tmp_path / "masque-2.txt").read_text(encoding="utf-8") == "DUPONT Jean"
    assert not (tmp_path / "masque-1.txt").exists()


def test_filtre_pour_une_image_d_apercu(tmp_path):
    masques = [boite(id=1), boite(id=2, start=8.0, end=9.0)]
    filtre = masks_filter(masques, 1920, 1080, 30, tmp_path, at=3.0)
    assert filtre.count("drawbox") == 1 and "enable" not in filtre
    assert masks_filter(masques, 1920, 1080, 30, tmp_path, at=6.0) is None
