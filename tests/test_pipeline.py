import shutil

import numpy as np
import pytest

from doublage import media
from doublage.cli import main
from doublage.pipeline import dub_project, dub_video, transcribe_video
from doublage.segments import Segment, Status, Transcript
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


class CompteSynthese(FakeSynthesizer):
    def __init__(self):
        super().__init__()
        self.textes = []

    def synthesize(self, text):
        self.textes.append(text)
        return super().synthesize(text)


def sans_ffmpeg(monkeypatch):
    """Remplace les appels à ffmpeg : la « vidéo doublée » est la bande son elle-même."""
    monkeypatch.setattr(media, "probe_duration", lambda video: 5.0)
    monkeypatch.setattr(media, "replace_audio", lambda video, audio, output: output.write_bytes(audio.read_bytes()))


def test_doublage_d_un_projet_reprend_les_voix_a_jour(tmp_path, monkeypatch):
    sans_ffmpeg(monkeypatch)
    Transcript(5.0, [Segment(0, 0.0, 2.0, "Un.", "Un."), Segment(1, 2.0, 4.0, "Deux.", "Deux.")]).save(
        tmp_path / "segments.json")
    synth = CompteSynthese()
    sortie = tmp_path / "video_doublee.mp4"
    dub_project(tmp_path / "video.mp4", tmp_path, sortie, synth, progress=lambda m: None)
    assert synth.textes == ["Un.", "Deux."] and sortie.exists()
    assert not (tmp_path / "video_doublee.partiel.mp4").exists()

    # Seule la phrase corrigée est régénérée ; l'autre garde sa voix.
    transcript = Transcript.load(tmp_path / "segments.json")
    transcript.set_text(1, "Deux et trois.")
    transcript.save(tmp_path / "segments.json")
    synth.textes.clear()
    dub_project(tmp_path / "video.mp4", tmp_path, sortie, synth, progress=lambda m: None)
    assert synth.textes == ["Deux et trois."]
    assert all(s.status == Status.SYNTHESIZED for s in Transcript.load(tmp_path / "segments.json").segments)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_changement_de_tempo_sans_changer_la_hauteur():
    sr = 24000
    t = np.arange(2 * sr) / sr
    signal = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    plus_vite = media.change_tempo(signal, sr, 1.25)
    assert len(plus_vite) / sr == pytest.approx(1.6, abs=0.05)
    freq = abs(np.fft.rfft(plus_vite)).argmax() * sr / len(plus_vite)
    assert freq == pytest.approx(440, abs=10)  # même hauteur de voix
