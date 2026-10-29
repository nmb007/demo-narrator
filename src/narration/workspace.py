"""Local and remote pipeline workspaces."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from src.narration import utils as key_utils
from src.narration.constants import (
    AUDIO,
    CLIPS,
    FINAL,
    NARRATION,
    SCRIPT,
    SOURCE,
    SYNC_REPORT,
    TRANSCRIPT,
    NarrationStep,
)
from src.narration.pipeline.paths import WorkPaths, resolve_workdir, work_paths
from src.storage import service as storage

logger = logging.getLogger(__name__)

ARTIFACT_TO_WORK_NAME = {
    AUDIO: "audio.wav",
    TRANSCRIPT: "transcript.json",
    SCRIPT: "script.json",
    CLIPS: "clips",
    NARRATION: "narration.wav",
    SYNC_REPORT: "sync-report.json",
}


class BaseWorkspace:
    def __init__(
        self,
        *,
        video_id: UUID,
        run_id: UUID,
        source_ext: str,
        paths: WorkPaths,
    ) -> None:
        self.video_id = video_id
        self.run_id = run_id
        self.source_ext = source_ext
        self.paths = paths

    def prepare(self, required: set[str]) -> None:
        raise NotImplementedError

    def after_step(self, step: NarrationStep) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def needs_source_for_voice(self) -> bool:
        if not self.paths.script.exists():
            return True
        script = json.loads(self.paths.script.read_text(encoding="utf-8"))
        return not script.get("video_duration")


class LocalWorkspace(BaseWorkspace):
    def prepare(self, required: set[str]) -> None:
        self.paths.work_dir.mkdir(parents=True, exist_ok=True)
        self.paths.final.parent.mkdir(parents=True, exist_ok=True)
        for artifact in required:
            if artifact == SOURCE:
                if not self.paths.source.is_file():
                    raise FileNotFoundError(f"Missing source video: {self.paths.source}")
            elif artifact == CLIPS:
                if not self.paths.clips_dir.is_dir():
                    raise FileNotFoundError(f"Missing clips directory: {self.paths.clips_dir}")
            else:
                path = _artifact_path(self.paths, artifact)
                if not path.exists():
                    raise FileNotFoundError(
                        f"Missing {artifact}. Run earlier pipeline steps first: {path}"
                    )

    def after_step(self, step: NarrationStep) -> None:
        return


class RemoteWorkspace(BaseWorkspace):
    def __init__(
        self,
        *,
        video_id: UUID,
        run_id: UUID,
        source_ext: str,
        paths: WorkPaths,
        tmp: TemporaryDirectory[str],
    ) -> None:
        super().__init__(
            video_id=video_id,
            run_id=run_id,
            source_ext=source_ext,
            paths=paths,
        )
        self._tmp = tmp

    def prepare(self, required: set[str]) -> None:
        self.paths.work_dir.mkdir(parents=True, exist_ok=True)
        self.paths.final.parent.mkdir(parents=True, exist_ok=True)
        for artifact in required:
            if artifact == SOURCE:
                key = key_utils.source_key(self.video_id, self.source_ext)
                storage.download(key, self.paths.source)
            elif artifact == CLIPS:
                # Download individual clip objects under work/clips/
                prefix = key_utils.work_key(self.video_id, "clips")
                keys = storage.list_keys(prefix)
                if not keys:
                    raise FileNotFoundError("Missing clips. Run voice first.")
                for key in keys:
                    rel = key[len(prefix) :].lstrip("/")
                    dest = self.paths.clips_dir / rel
                    storage.download(key, dest)
            else:
                name = ARTIFACT_TO_WORK_NAME[artifact]
                key = key_utils.work_key(self.video_id, name)
                if not storage.exists(key):
                    raise FileNotFoundError(
                        f"Missing {artifact}. Run earlier pipeline steps first."
                    )
                storage.download(key, _artifact_path(self.paths, artifact))

    def after_step(self, step: NarrationStep) -> None:
        from src.narration.constants import STEP_WRITES

        for artifact in STEP_WRITES[step]:
            if artifact == FINAL:
                storage.upload(self.paths.final, key_utils.final_key(self.video_id, self.run_id))
            elif artifact == CLIPS:
                storage.upload_dir(
                    self.paths.clips_dir,
                    key_utils.work_key(self.video_id, "clips"),
                )
            else:
                path = _artifact_path(self.paths, artifact)
                if path.exists():
                    name = ARTIFACT_TO_WORK_NAME[artifact]
                    storage.upload(path, key_utils.work_key(self.video_id, name))

    def close(self) -> None:
        self._tmp.cleanup()


def open_workspace(
    *,
    video_id: UUID,
    run_id: UUID,
    source_ext: str,
) -> BaseWorkspace:
    if storage.is_local():
        source = storage.local_path(key_utils.source_key(video_id, source_ext))
        work_dir = resolve_workdir(storage.local_path(key_utils.work_key(video_id, "")))
        final = storage.local_path(key_utils.final_key(video_id, run_id))
        paths = work_paths(work_dir, source=source, final=final)
        return LocalWorkspace(
            video_id=video_id,
            run_id=run_id,
            source_ext=source_ext,
            paths=paths,
        )

    tmp = TemporaryDirectory(prefix="narration-work-")
    root = Path(tmp.name)
    source = root / f"source.{source_ext}"
    work_dir = resolve_workdir(root / "work")
    final = root / "final.mp4"
    paths = work_paths(work_dir, source=source, final=final)
    return RemoteWorkspace(
        video_id=video_id,
        run_id=run_id,
        source_ext=source_ext,
        paths=paths,
        tmp=tmp,
    )


def _artifact_path(paths: WorkPaths, artifact: str) -> Path:
    mapping = {
        AUDIO: paths.audio,
        TRANSCRIPT: paths.transcript,
        SCRIPT: paths.script,
        CLIPS: paths.clips_dir,
        NARRATION: paths.narration,
        SYNC_REPORT: paths.sync_report,
        FINAL: paths.final,
        SOURCE: paths.source,
    }
    return mapping[artifact]
