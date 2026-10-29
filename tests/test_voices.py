from doublage.voices import Voice, VoiceCatalog


def test_catalogue():
    catalog = VoiceCatalog(["estelle", "", "bill_boerst", "estelle"], "estelle")
    assert [v.id for v in catalog.list()] == ["estelle", "bill_boerst"]
    assert catalog.get("bill_boerst") == Voice("bill_boerst", "Bill Boerst", "bill_boerst")
    assert catalog.get("inconnue") is None


def test_voix_du_projet():
    catalog = VoiceCatalog(["estelle", "alba"], "estelle")
    assert catalog.for_project(None).id == "estelle"
    assert catalog.for_project("alba").id == "alba"
    assert catalog.for_project("retiree").id == "estelle"  # retirée du catalogue : voix par défaut
    assert VoiceCatalog(["alba"], "estelle").for_project(None).id == "estelle"


def faux_echantillon(secondes):
    """Remplace la conversion ffmpeg : écrit un WAV de la durée voulue."""
    import numpy as np

    from doublage import media

    def prepare(source, wav, max_seconds):
        assert max_seconds == 10  # au-delà, Pocket TTS coupe les phrases générées
        if source.read_bytes() == b"illisible":
            raise media.MediaError("format inconnu")
        return media.write_wav(wav, np.zeros(int(secondes * 24000), dtype=np.float32), 24000)
    return prepare


def test_ajout_et_suppression_d_une_voix(tmp_path):
    import io

    import pytest

    from doublage.voices import VoiceError

    catalog = VoiceCatalog(["estelle"], "estelle", tmp_path / "voix")
    voix = catalog.add("  Élodie  Martin ", io.BytesIO(b"son"), "alice", faux_echantillon(10))
    assert voix.label == "Élodie Martin" and voix.added_by == "alice"
    assert voix.id.startswith("elodie-martin-") and voix.ref.endswith(".wav")
    assert [v.id for v in catalog.list()] == ["estelle", voix.id]
    assert catalog.for_project(voix.id) == voix
    assert not list((tmp_path / "voix").glob("*.source"))  # fichier déposé effacé après conversion

    with pytest.raises(VoiceError, match="déjà"):
        catalog.add("élodie martin", io.BytesIO(b"son"), "bob", faux_echantillon(10))
    with pytest.raises(VoiceError, match="trop court"):
        catalog.add("Court", io.BytesIO(b"son"), "bob", faux_echantillon(1))
    with pytest.raises(VoiceError, match="illisible"):
        catalog.add("Cassé", io.BytesIO(b"illisible"), "bob", faux_echantillon(10))
    with pytest.raises(VoiceError, match="nom"):
        catalog.add("  ", io.BytesIO(b"son"), "bob", faux_echantillon(10))
    assert len(catalog.custom()) == 1 and len(list((tmp_path / "voix").iterdir())) == 2  # WAV + fiche

    (tmp_path / "voix" / f"{voix.id}.french.safetensors").write_bytes(b"etat")  # préparé par le moteur
    catalog.delete(voix.id)
    assert catalog.custom() == [] and list((tmp_path / "voix").iterdir()) == []
    with pytest.raises(KeyError):
        catalog.delete("estelle")
