import numpy as np
import pytest

from doublage.assembly import Fit, assemble, fit
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
