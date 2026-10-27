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
