import pytest

from doublage import media
from doublage.cli import main
from doublage.pipeline import dub_video, transcribe_video
from doublage.segments import Status, Transcript
from doublage.transcription import FakeTranscriber
from doublage.tts import FakeSynthesizer


def test_extraction_audio(sample_video, tmp_path):
    wav = media.extract_audio(sample_video, tmp_path / "a.wav")
    audio, sr = media.read_wav(wav)
    assert sr == 16000 and len(audio) / sr == pytest.approx(10, abs=0.1)


def test_chaine_complete(sample_video, tmp_path):
    workdir = tmp_path / "projet"
    transcript = transcribe_video(sample_video, workdir, FakeTranscriber(), progress=lambda m: None)
    assert (workdir / "segments.json").exists()

    sortie = tmp_path / "double.mp4"
    placements = dub_video(sample_video, transcript, workdir, sortie, FakeSynthesizer(),
                           progress=lambda m: None)
    assert len(placements) == 3
    assert media.probe_duration(sortie) == pytest.approx(10, abs=0.3)
    assert all(s.status == Status.SYNTHESIZED for s in Transcript.load(workdir / "segments.json").segments)
    assert len(list((workdir / "phrases").glob("*.wav"))) == 3

    # La nouvelle bande son est bien celle de la voix synthétique (440 Hz), pas l'originale (300 Hz).
    audio, sr = media.read_wav(media.extract_audio(sortie, tmp_path / "verif.wav"))
    extrait = audio[int(0.2 * sr):int(1.0 * sr)]
    freq = abs(__import__("numpy").fft.rfft(extrait)).argmax() * sr / len(extrait)
    assert freq == pytest.approx(440, abs=10)


def test_commande_traiter_simulee(sample_video, tmp_path, capsys):
    sortie = tmp_path / "out.mp4"
    main(["traiter", str(sample_video), "-o", str(sortie), "--dossier", str(tmp_path / "w"), "--simuler"])
    assert sortie.exists()
    assert "Vidéo doublée" in capsys.readouterr().out
