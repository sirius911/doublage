import numpy as np
import pytest

from doublage.assembly import Fit, assemble, fit, fit_clips, speed_factor
from doublage.segments import Segment, Transcript

SR = 100


def test_placement_au_timecode():
    clips = [(0, 1.0, np.ones(50, np.float32)), (1, 3.0, np.ones(20, np.float32))]
    track, placements = assemble(clips, 5.0, SR)
    assert len(track) == 500
    assert track[:100].sum() == 0 and track[100:150].sum() == 50 and track[150:300].sum() == 0
    assert [p.delay for p in placements] == [0, 0]


def test_debordement_decale_la_suivante():
    clips = [(0, 0.0, np.ones(250, np.float32)), (1, 2.0, np.ones(50, np.float32))]
    track, placements = assemble(clips, 3.0, SR)
    assert placements[1].start == pytest.approx(2.5)
    assert placements[1].delay == pytest.approx(0.5)
    assert track.max() == 1  # pas de superposition
    assert len(track) == 300


def test_piste_allongee_si_necessaire():
    track, _ = assemble([(0, 0.5, np.ones(100, np.float32))], 1.0, SR)
    assert len(track) == 150


def test_calage_dans_le_creneau():
    t = Transcript(10.0, [Segment(0, 1.0, 3.0, "a", "a"), Segment(1, 4.0, 6.0, "b", "b")])
    premier, dernier = t.segments
    assert t.slot_end(premier) == 4.0 and t.slot_end(dernier) == 10.0
    assert fit(premier, 4.0, 2.0)[0] == Fit.OK
    assert fit(premier, 4.0, 2.03)[0] == Fit.OK  # écart inaudible
    niveau, texte = fit(premier, 4.0, 2.8)
    assert niveau == Fit.OVERFLOW and "2,8 s" in texte and "2,0 s" in texte
    niveau, texte = fit(premier, 4.0, 3.5)
    assert niveau == Fit.OVERLAP and "0,5 s" in texte


def test_acceleration_legere():
    phrase = Segment(0, 1.0, 3.0, "a", "a")  # créneau : jusqu'à 4,0 (3 s disponibles)
    assert speed_factor(phrase, 4.0, 2.9, 1.15) == 1.0  # tient en débordant sur le silence
    assert speed_factor(phrase, 4.0, 3.3, 1.15) == pytest.approx(1.1)
    assert speed_factor(phrase, 4.0, 6.0, 1.15) == 1.15  # plafonnée
    niveau, texte = fit(phrase, 4.0, 3.3, 1.15)
    assert niveau == Fit.OVERFLOW and "accélérée de 10 %" in texte
    niveau, texte = fit(phrase, 4.0, 3.3, 1.0)  # accélération désactivée
    assert niveau == Fit.OVERLAP and "Même" not in texte
    assert fit(phrase, 4.0, 3.6, 1.15)[0] == Fit.OVERLAP


def test_seules_les_voix_qui_empietent_sont_accelerees():
    t = Transcript(10.0, [Segment(0, 0.0, 2.0, "a", "a"), Segment(1, 3.0, 5.0, "b", "b")])
    clips = [(0, 0.0, np.ones(330, np.float32)), (1, 3.0, np.ones(250, np.float32))]
    appels = []

    def tempo(audio, sr, vitesse):
        appels.append(vitesse)
        return audio[:int(len(audio) / vitesse)]

    resultat, n, ralenties = fit_clips(t, clips, SR, 1.15, tempo)
    assert n == 1 and ralenties == 0 and appels == [pytest.approx(1.1)]
    assert len(resultat[0][2]) == 300 and len(resultat[1][2]) == 250


def test_ralentissement_des_voix_courtes():
    phrase = Segment(0, 0.0, 2.0, "a", "a")
    assert speed_factor(phrase, 4.0, 1.9, 1.15, 0.9) == pytest.approx(0.95)
    assert speed_factor(phrase, 4.0, 1.0, 1.15, 0.9) == 0.9  # plafonné
    assert speed_factor(phrase, 4.0, 1.97, 1.15, 0.9) == 1.0  # écart négligeable
    assert speed_factor(phrase, 4.0, 1.0, 1.15) == 1.0  # ralentissement désactivé par défaut
    niveau, texte = fit(phrase, 4.0, 1.9, 1.15, 0.9)
    assert niveau == Fit.OK and "ralentie de 5 %" in texte
    assert "ralentie" not in fit(phrase, 4.0, 1.9, 1.15)[1]

    t = Transcript(10.0, [phrase, Segment(1, 3.0, 5.0, "b", "b", keep_original=True)])
    clips = [(0, 0.0, np.ones(190, np.float32)), (1, 3.0, np.ones(150, np.float32))]
    appels = []

    def tempo(audio, sr, vitesse):
        appels.append(vitesse)
        return np.ones(int(len(audio) / vitesse), np.float32)

    resultat, accelerees, ralenties = fit_clips(t, clips, SR, 1.15, tempo, 0.9)
    assert (accelerees, ralenties) == (0, 1) and appels == [pytest.approx(0.95)]  # son d'origine intact
    assert len(resultat[0][2]) == 200 and len(resultat[1][2]) == 150


def test_vitesse_reglee_a_la_main():
    phrase = Segment(0, 0.0, 2.0, "a", "a", speed=1.1)
    niveau, texte = fit(phrase, 3.0, 2.2, 1.15, 0.9)  # 2,2 s à ×1,1 = 2,0 s
    assert niveau == Fit.OK and "réglée à la main" in texte and "accélérée de 10 %" in texte
    phrase.speed = 0.8  # 2,2 s → 2,75 s : finit avant la phrase suivante (3,0)
    assert fit(phrase, 3.0, 2.2)[0] == Fit.OVERFLOW
    assert fit(phrase, 2.5, 2.2)[0] == Fit.OVERLAP

    t = Transcript(10.0, [phrase])
    appels = []
    fit_clips(t, [(0, 0.0, np.ones(220, np.float32))], SR, 1.15,
              lambda audio, sr, v: appels.append(v) or audio, 0.9)
    assert appels == [0.8]  # la vitesse choisie remplace la vitesse automatique
