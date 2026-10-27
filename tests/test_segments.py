import pytest

from doublage.segments import Segment, Status, Transcript


def test_aller_retour_json(tmp_path):
    t = Transcript(duration=12.5, segments=[
        Segment(0, 0.0, 2.5, "Bonjour à tous.", "Bonjour à toutes et à tous."),
        Segment(1, 3.0, 6.0, "Cliquez ici.", "Cliquez ici.", Status.SYNTHESIZED),
    ])
    path = tmp_path / "segments.json"
    t.save(path)
    assert "Bonjour à tous" in path.read_text(encoding="utf-8")  # accents non échappés
    assert Transcript.load(path) == t
    assert t.segments[0].duration == 2.5


def test_correction_du_texte():
    t =Transcript(10.0, [Segment(0, 0.0, 2.0, "Bonjour", "Bonjour"),
                          Segment(1, 2.0, 4.0, "Zim bra", "Zim bra", Status.SYNTHESIZED)])
    assert t.set_text(0, "  Bonjour   à tous\n").text == "Bonjour à tous"
    assert t.segments[0].status == Status.TRANSCRIBED and t.segments[0].original_text == "Bonjour"
    assert t.set_text(1, "Zim bra").status == Status.SYNTHESIZED  # inchangé : la voix reste valable
    assert t.set_text(1, "Zimbra").status == Status.MODIFIED
    with pytest.raises(KeyError):
        t.set_text(99, "x")
