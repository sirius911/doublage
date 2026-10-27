import threading

from doublage.jobs import JobManager, JobState


def test_traitement_reussi():
    jobs = JobManager()
    etapes = []

    def travail(progress):
        progress("Étape 1")
        etapes.append(jobs.get(1).step)

    jobs.submit(1, "transcription", travail)
    jobs.wait(1, timeout=5)
    job = jobs.get(1)
    assert job.state == JobState.DONE and not job.active
    assert etapes == ["Étape 1"]


def test_traitement_en_erreur():
    jobs = JobManager()

    def travail(progress):
        raise RuntimeError("Le serveur Whisper n'a pas répondu")

    jobs.submit(1, "transcription", travail)
    jobs.wait(1, timeout=5)
    assert jobs.get(1).state == JobState.FAILED
    assert "Whisper" in jobs.get(1).error


def test_pas_de_doublon_et_un_seul_a_la_fois():
    jobs = JobManager()
    libere = threading.Event()
    lances = []

    def travail(progress):
        lances.append(1)
        libere.wait(5)

    premier = jobs.submit(1, "transcription", travail)
    assert jobs.submit(1, "transcription", travail) is premier  # déjà en cours : pas relancé
    jobs.submit(2, "transcription", travail)
    assert jobs.get(2).state == JobState.WAITING  # attend la fin du premier
    libere.set()
    jobs.wait(1, timeout=5)
    jobs.wait(2, timeout=5)
    assert len(lances) == 2
