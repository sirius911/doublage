import httpx
import numpy as np
import pytest

from doublage.transcription import (
    FakeTranscriber, TranscriptionError, WhisperApiTranscriber, is_hallucination, parse_verbose_json, regroup,
    trim_silences,
)
from doublage.segments import Segment, Transcript

REPONSE = {
    "text": "Bonjour. Ouvrez le menu.",
    "duration": 8.2,
    "segments": [
        {"id": 0, "start": 0.0, "end": 1.4, "text": " Bonjour."},
        {"id": 1, "start": 2.0, "end": 4.1, "text": " Ouvrez le menu."},
        {"id": 2, "start": 4.5, "end": 5.0, "text": "  "},
    ],
}


def test_parse_verbose_json():
    t = parse_verbose_json(REPONSE)
    assert t.duration == 8.2
    assert [(s.id, s.start, s.end, s.text) for s in t.segments] == [
        (0, 0.0, 1.4, "Bonjour."), (1, 2.0, 4.1, "Ouvrez le menu."),
    ]
    assert t.segments[0].original_text == t.segments[0].text


def test_parse_sans_segments():
    with pytest.raises(TranscriptionError):
        parse_verbose_json({"text": "Bonjour", "duration": 1.0})


def test_appel_api(tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF....")
    recu = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recu["url"] = str(request.url)
        recu["corps"] = request.read()
        return httpx.Response(200, json=REPONSE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = WhisperApiTranscriber("http://whisper/v1/audio/transcriptions", client=client).transcribe(audio)
    assert len(t.segments) == 2
    assert recu["url"] == "http://whisper/v1/audio/transcriptions"
    corps = recu["corps"]
    assert b'name="file"; filename="a.wav"' in corps
    assert b"verbose_json" in corps and b'name="language"' in corps
    assert b'name="model"' not in corps and b'name="prompt"' not in corps

    WhisperApiTranscriber("http://whisper/", prompt="Bonjour, voici un exemple.", client=client).transcribe(audio)
    assert 'name="prompt"\r\n\r\nBonjour, voici un exemple.'.encode() in recu["corps"]


def test_erreur_serveur(tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(TranscriptionError):
        WhisperApiTranscriber("http://whisper/", client=client).transcribe(audio)


def test_transcription_simulee(sample_video):
    t = FakeTranscriber().transcribe(sample_video)
    assert len(t.segments) == 3 and t.duration == pytest.approx(10, abs=0.2)


def test_whisper_sans_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.exemple:8080")
    monkeypatch.setenv("http_proxy", "http://proxy.exemple:8080")
    assert WhisperApiTranscriber("http://10.0.0.1/v1/audio/transcriptions").client.trust_env is False


def test_fin_bornee_a_la_duree():
    # Réponse réelle du serveur interne sur un bip de 2 s.
    t = parse_verbose_json({"duration": 2.0, "text": "Sous-titrage ST' 501",
                            "segments": [{"start": 0.0, "end": 29.98, "text": " Sous-titrage ST' 501"}]})
    assert (t.segments[0].start, t.segments[0].end) == (0.0, 2.0)


def test_timecodes_arrondis_a_la_milliseconde():
    t = parse_verbose_json({"duration": 20.0, "segments": [
        {"start": 6.1000000000000005, "end": 14.780000000000001, "text": "Ensuite."}]})
    assert (t.segments[0].start, t.segments[0].end) == (6.1, 14.78)


def test_regroupement_des_troncons_d_une_phrase():
    t = regroup(Transcript(30.0, [
        Segment(0, 0.0, 2.0, "Ouvrez", "Ouvrez"),
        Segment(1, 2.0, 3.5, "le menu.", "le menu."),  # fin de phrase
        Segment(2, 3.5, 5.0, "Puis cliquez", "Puis cliquez"),
        Segment(3, 6.5, 8.0, "sur Valider.", "sur Valider."),  # silence de 1,5 s : pas réunis
        Segment(4, 8.0, 15.0, "Une phrase", "Une phrase"),
        Segment(5, 15.0, 24.0, "trop longue", "trop longue"),  # dépasserait 15 s : pas réunis
    ]))
    assert [(s.id, s.start, s.end, s.text) for s in t.segments] == [
        (0, 0.0, 3.5, "Ouvrez le menu."), (1, 3.5, 5.0, "Puis cliquez"), (2, 6.5, 8.0, "sur Valider."),
        (3, 8.0, 15.0, "Une phrase"), (4, 15.0, 24.0, "trop longue"),
    ]
    assert t.segments[0].original_text == "Ouvrez le menu." and t.duration == 30.0


def test_hallucinations_ecartees():
    boucle = " ".join(["je peux avoir des noms propres et"] * 15)
    assert is_hallucination(boucle)
    assert not is_hallucination("Ouvrez le menu, puis cliquez sur « Nouveau message » en haut à gauche de "
                                "l'écran : une fenêtre s'ouvre, dans laquelle vous saisissez l'adresse.")
    t = parse_verbose_json({"duration": 30.0, "segments": [
        {"start": 0.0, "end": 2.0, "text": "Bonjour."},
        {"start": 2.0, "end": 12.0, "text": boucle},  # boucle dans un seul tronçon
        *({"start": 12.0 + i, "end": 13.0 + i, "text": "je peux avoir des noms propres et"}
          for i in range(10)),  # boucle répartie sur plusieurs tronçons
    ]})
    assert [(s.id, s.text) for s in t.segments] == [(0, "Bonjour.")]


def test_debut_recale_sur_la_parole():
    # 6 s de silence puis de la parole jusqu'à 10 s ; Whisper annonce la première phrase à 0 s.
    sr = 16000
    audio = np.zeros(10 * sr, dtype=np.float32)
    audio[6 * sr:] = 0.3 * np.sin(np.arange(4 * sr) * 2 * np.pi * 200 / sr)
    audio[int(8.1 * sr):int(8.5 * sr)] = 0  # pause courte au début de la deuxième phrase
    t = Transcript(duration=10, segments=[
        Segment(id=0, start=0.0, end=8.0, original_text="Bonjour.", text="Bonjour."),
        Segment(id=1, start=8.1, end=10.0, original_text="Suite.", text="Suite."),
        Segment(id=2, start=9.0, end=9.0, original_text="Vide.", text="Vide."),
    ])
    trim_silences(t, audio, sr)
    assert t.segments[0].start == pytest.approx(5.9, abs=0.03)
    assert t.segments[0].end == 8.0  # pas de silence à la fin
    assert t.segments[1].start == pytest.approx(8.4, abs=0.03)
    assert t.segments[2].start == 9.0


def test_debut_inchange_sans_silence_ou_sans_son():
    sr = 16000
    t = Transcript(duration=2, segments=[Segment(id=0, start=0.0, end=2.0, original_text="A.", text="A.")])
    trim_silences(t, np.full(2 * sr, 0.2, dtype=np.float32), sr)
    assert t.segments[0].start == 0.0
    trim_silences(t, np.zeros(2 * sr, dtype=np.float32), sr)
    assert t.segments[0].start == 0.0


def test_fin_recalee_avant_la_pause():
    # Parole de 1 s à 3 s, puis silence ; Whisper étire la phrase jusqu'au début de la suivante (6 s).
    sr = 16000
    audio = np.zeros(8 * sr, dtype=np.float32)
    audio[1 * sr:3 * sr] = 0.3 * np.sin(np.arange(2 * sr) * 2 * np.pi * 200 / sr)
    audio[6 * sr:] = 0.3 * np.sin(np.arange(2 * sr) * 2 * np.pi * 200 / sr)
    t = Transcript(duration=8, segments=[
        Segment(id=0, start=1.0, end=6.0, original_text="A.", text="A."),
        Segment(id=1, start=6.0, end=8.0, original_text="B.", text="B."),
    ])
    trim_silences(t, audio, sr)
    assert t.segments[0].start == 1.0
    assert t.segments[0].end == pytest.approx(3.2, abs=0.03)
    assert (t.segments[1].start, t.segments[1].end) == (6.0, 8.0)
    # Le créneau (jusqu'à la phrase suivante) ne change pas : la voix peut toujours déborder sur la pause.
    assert t.slot_end(t.segments[0]) == 6.0
