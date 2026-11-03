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


def test_marge_d_une_image_et_demie():
    lo, hi = boite().window(30)
    assert lo == pytest.approx(1.95) and hi == pytest.approx(4.05)
    assert boite(start=0.0).window(30)[0] == 0.0
    assert boite().visible_at(1.96, 30) and not boite().visible_at(4.1, 30)


def test_filtre_ffmpeg(tmp_path):
    assert masks_filter([], 1920, 1080, 30, tmp_path) is None
    filtre = masks_filter([boite(), boite(id=2, text=" DUPONT Jean ", background="#eeeeee")],
                          1920, 1080, 30, tmp_path)
    cache, fond, texte = filtre.split(",drawbox", 1)[0], *filtre.split(",drawbox", 1)[1].split(",drawtext")
    assert cache == "drawbox=x=192:y=216:w=576:h=54:color=0xffffff@1:t=fill:enable='between(t,1.9500,4.0500)'"
    assert "color=0xeeeeee@1" in fond
    assert "textfile=masque-2.txt" in texte and "expansion=none" in texte and "fontsize=38" in texte
    assert texte.endswith(":enable='between(t,1.9500,4.0500)'")
    assert (tmp_path / "masque-2.txt").read_text(encoding="utf-8") == "DUPONT Jean"
    assert not (tmp_path / "masque-1.txt").exists()


def test_filtre_pour_une_image_d_apercu(tmp_path):
    masques = [boite(id=1), boite(id=2, start=8.0, end=9.0)]
    filtre = masks_filter(masques, 1920, 1080, 30, tmp_path, at=3.0)
    assert filtre.count("drawbox") == 1 and "enable" not in filtre
    assert masks_filter(masques, 1920, 1080, 30, tmp_path, at=6.0) is None
