import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """Vidéo de 10 s (mire + bip), générée par ffmpeg."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg absent (il est installé en intégration continue)")
    path = tmp_path_factory.mktemp("media") / "tuto.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=10",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True)
    return path
