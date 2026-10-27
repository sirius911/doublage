"""Traitements longs (transcription, synthèse…) exécutés en tâche de fond, un à la fois."""

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum

Progress = Callable[[str], None]


class JobState(StrEnum):
    WAITING = "en_attente"
    RUNNING = "en_cours"
    DONE = "termine"
    FAILED = "erreur"


@dataclass
class Job:
    kind: str  # « transcription », « synthese »…
    state: JobState = JobState.WAITING
    step: str = "En attente…"
    error: str = ""
    started: float = field(default_factory=time.time)

    @property
    def active(self) -> bool:
        return self.state in (JobState.WAITING, JobState.RUNNING)


class JobManager:
    """Un seul traitement à la fois : la VM est partagée et la synthèse occupe le processeur.

    L'état est gardé en mémoire : un redémarrage de l'application oublie les traitements en cours
    (il suffit de les relancer ; les résultats terminés sont, eux, enregistrés dans le projet).
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="traitement")
        self._jobs: dict[int, Job] = {}
        self._futures: dict[int, Future] = {}
        self._lock = threading.Lock()

    def get(self, project_id: int) -> Job | None:
        return self._jobs.get(project_id)

    def submit(self, project_id: int, kind: str, work: Callable[[Progress], object]) -> Job:
        """Lance `work(progress)` en tâche de fond, sauf si un traitement du projet est déjà prévu."""
        with self._lock:
            job = self._jobs.get(project_id)
            if job and job.active:
                return job
            job = Job(kind)
            self._jobs[project_id] = job
            self._futures[project_id] = self._executor.submit(self._run, job, work)
            return job

    @staticmethod
    def _run(job: Job, work: Callable[[Progress], object]) -> None:
        job.state, job.started = JobState.RUNNING, time.time()

        def progress(message: str) -> None:
            job.step = message

        try:
            work(progress)
        except Exception as e:  # l'erreur est affichée dans l'interface
            job.state, job.error = JobState.FAILED, str(e) or type(e).__name__
        else:
            job.state, job.step = JobState.DONE, "Terminé."

    def wait(self, project_id: int, timeout: float | None = None) -> None:
        future = self._futures.get(project_id)
        if future:
            future.result(timeout)
