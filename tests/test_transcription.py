import httpx
import pytest

from doublage.transcription import (
    FakeTranscriber, TranscriptionError, WhisperApiTranscriber, parse_verbose_json,
)

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
    assert b'name="model"' not in corps


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
