"""Essai réel de Pocket TTS (lent ; télécharge le modèle). Lancer avec : pytest -m tts"""

import pytest

pytestmark = pytest.mark.tts


def test_pocket_tts_francais():
    from doublage.tts import PocketSynthesizer

    synth = PocketSynthesizer("french", "estelle")
    audio = synth.synthesize("Cliquez sur le bouton Enregistrer.")
    assert 0.5 < len(audio) / synth.sample_rate < 10
