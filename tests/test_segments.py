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
