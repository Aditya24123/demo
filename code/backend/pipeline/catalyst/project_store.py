from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from catalyst.settings import utc_now


PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
MAX_PROJECT_ID_LENGTH = 64
MAX_PROJECT_NAME_LENGTH = 120
MAX_PROJECT_DESCRIPTION_LENGTH = 500
MAX_NOTEBOOK_BYTES = 2 * 1024 * 1024
NOTEBOOK_FILE = "research.md"
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
EDITABLE_ROOTS = {"files", "notebook", "artifacts"}
EDITABLE_SUFFIXES = {
    ".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml",
    ".py", ".js", ".mjs", ".ts", ".tsx", ".html", ".css", ".toml",
    ".keep",  # empty-folder markers for user-created directories
}


def sanitize_project_id(value: str) -> str:
    """Turn user input into a portable, path-safe project identifier."""
    normalized = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    slug = slug[:MAX_PROJECT_ID_LENGTH].strip("-_")
    return slug


class ProjectStore:
    """Persistent project metadata and bounded project directories."""

    def __init__(self, repo_root: Path) -> None:
        self.root = (Path(repo_root) / "data" / "workspaces").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_project_id(self, project_id: str) -> str:
        candidate = str(project_id or "").strip()
        if not candidate or not PROJECT_ID_PATTERN.fullmatch(candidate):
            raise ValueError("project_id must contain only lowercase letters, numbers, hyphens, or underscores")
        return candidate

    def _project_path(self, project_id: str) -> Path:
        safe_id = self._validate_project_id(project_id)
        path = (self.root / safe_id).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("project path escapes the workspace root") from exc
        return path

    def project_path(self, project_id: str) -> Path:
        """Return an existing project root bounded to the workspace directory."""
        path = self._project_path(project_id)
        if not path.is_dir() or self._read_metadata(path / "project.json") is None:
            raise FileNotFoundError(f"Project not found: {project_id}")
        return path

    @staticmethod
    def _read_metadata(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        required = {"project_id", "name", "created_at", "updated_at", "archived"}
        if not required.issubset(payload):
            return None
        return payload

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def list_projects(self, include_archived: bool = False) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for directory in self.root.iterdir():
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            metadata = self._read_metadata(directory / "project.json")
            if not metadata or (metadata.get("archived", False) and not include_archived):
                continue
            projects.append(metadata)
        return sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        path = self._project_path(project_id)
        if not path.is_dir():
            return None
        return self._read_metadata(path / "project.json")

    def create_project(
        self,
        *,
        name: str,
        project_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("name is required")
        if len(clean_name) > MAX_PROJECT_NAME_LENGTH:
            raise ValueError(f"name must be {MAX_PROJECT_NAME_LENGTH} characters or fewer")

        requested_id = sanitize_project_id(project_id) if project_id else sanitize_project_id(clean_name)
        if not requested_id:
            requested_id = f"project-{uuid4().hex[:8]}"
        requested_id = self._validate_project_id(requested_id)
        clean_description = str(description).strip() if description is not None else None
        if clean_description and len(clean_description) > MAX_PROJECT_DESCRIPTION_LENGTH:
            raise ValueError(f"description must be {MAX_PROJECT_DESCRIPTION_LENGTH} characters or fewer")

        for suffix in range(0, 1000):
            candidate = requested_id if suffix == 0 else f"{requested_id[:MAX_PROJECT_ID_LENGTH - len(str(suffix)) - 1]}-{suffix}"
            target = self._project_path(candidate)
            if target.exists():
                continue
            staging = self.root / f".{candidate}.creating-{uuid4().hex}"
            try:
                staging.mkdir()
                for child in ("files", "artifacts", "notebook", "runs", "exports", ".catalyst"):
                    (staging / child).mkdir()
                now = utc_now()
                metadata: dict[str, Any] = {
                    "project_id": candidate,
                    "name": clean_name,
                    "created_at": now,
                    "updated_at": now,
                    "archived": False,
                }
                if clean_description:
                    metadata["description"] = clean_description
                self._write_json(staging / "project.json", metadata)
                (staging / "notebook" / NOTEBOOK_FILE).write_text(
                    f"# {clean_name}\n\n## Research notes\n\n",
                    encoding="utf-8",
                )
                try:
                    staging.replace(target)
                except FileExistsError:
                    continue
                return metadata
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
        raise ValueError("could not allocate a unique project id")

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        safe_id = self._validate_project_id(project_id)
        path = self._project_path(safe_id)
        metadata = self._read_metadata(path / "project.json") if path.is_dir() else None
        if metadata is None:
            return None
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("name cannot be empty")
            if len(clean_name) > MAX_PROJECT_NAME_LENGTH:
                raise ValueError(f"name must be {MAX_PROJECT_NAME_LENGTH} characters or fewer")
            metadata["name"] = clean_name
        if description is not None:
            clean_description = description.strip()
            if len(clean_description) > MAX_PROJECT_DESCRIPTION_LENGTH:
                raise ValueError(f"description must be {MAX_PROJECT_DESCRIPTION_LENGTH} characters or fewer")
            metadata["description"] = clean_description or None
        metadata["updated_at"] = utc_now()
        self._write_json(path / "project.json", metadata)
        return metadata

    def archive_project(self, project_id: str) -> dict[str, Any] | None:
        safe_id = self._validate_project_id(project_id)
        path = self._project_path(safe_id)
        metadata = self._read_metadata(path / "project.json") if path.is_dir() else None
        if metadata is None:
            return None
        metadata["archived"] = True
        metadata["updated_at"] = utc_now()
        self._write_json(path / "project.json", metadata)
        return metadata

    def delete_project(self, project_id: str) -> bool:
        """Permanently remove a project directory (no archive)."""
        path = self.project_path(project_id)
        shutil.rmtree(path)
        return True

    def ensure_folder(self, project_id: str, relative_path: str) -> dict[str, Any]:
        """Create an empty folder under files/notebook/artifacts via a .keep marker."""
        root = self.project_path(project_id)
        clean = str(relative_path or "").strip().replace("\\", "/").strip("/")
        if not clean:
            raise ValueError("folder path is required")
        # Force under editable roots.
        if not any(clean == root_name or clean.startswith(f"{root_name}/") for root_name in EDITABLE_ROOTS):
            clean = f"files/{clean}"
        # Folder itself has no suffix ? validate parent path parts without requiring a file type.
        folder_rel = Path(clean.rstrip("/"))
        if folder_rel.is_absolute() or ".." in folder_rel.parts or folder_rel.parts[0] not in EDITABLE_ROOTS:
            raise ValueError("project folders must stay inside files, notebook, or artifacts")
        folder_path = (root / folder_rel).resolve()
        try:
            folder_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("project folder path escapes the project root") from exc
        folder_path.mkdir(parents=True, exist_ok=True)
        keep = folder_path / ".keep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        self._touch_project(root)
        return {
            "path": folder_path.relative_to(root).as_posix(),
            "kind": "folder",
            "updated_at": utc_now(),
        }

    def workspace_snapshot(self, project_id: str) -> dict[str, Any]:
        root = self.project_path(project_id)
        files: list[dict[str, Any]] = []
        folder_set: set[str] = set(EDITABLE_ROOTS) | {"runs", "exports"}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part.startswith(".") for part in relative.parts):
                continue
            if path.is_dir():
                # Surface custom folders under editable roots.
                if relative.parts and relative.parts[0] in EDITABLE_ROOTS:
                    folder_set.add(relative.as_posix())
                continue
            if path.is_file():
                # .keep markers represent empty folders only ? skip as files.
                if path.name == ".keep":
                    folder_set.add(path.parent.relative_to(root).as_posix())
                    continue
                files.append({
                    "path": relative.as_posix(),
                    "size": path.stat().st_size,
                    "kind": "notebook" if relative.parts[0] == "notebook" else "file",
                })
            if len(files) >= 500:
                break
        state = self._read_json(root / ".catalyst" / "codex.json") or {}
        # Prefer top-level roots first, then nested custom folders.
        folders = sorted(
            folder_set,
            key=lambda item: (item.count("/"), item),
        )
        return {
            "project": self._read_metadata(root / "project.json"),
            "folders": folders,
            "files": files,
            "codex": {
                "thread_id": state.get("thread_id"),
                "last_run_at": state.get("last_run_at"),
            },
        }

    def read_text_file(self, project_id: str, relative_path: str) -> dict[str, Any]:
        root = self.project_path(project_id)
        path = self._editable_path(root, relative_path)
        if not path.is_file():
            raise FileNotFoundError(f"Project file not found: {relative_path}")
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            raise ValueError("project file must be 2 MB or smaller")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("project file is not UTF-8 text") from exc
        return {"path": path.relative_to(root).as_posix(), "content": content, "size": path.stat().st_size}

    def write_text_file(self, project_id: str, relative_path: str, content: str) -> dict[str, Any]:
        root = self.project_path(project_id)
        path = self._editable_path(root, relative_path)
        encoded = str(content).encode("utf-8")
        if len(encoded) > MAX_TEXT_FILE_BYTES:
            raise ValueError("project file must be 2 MB or smaller")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        self._touch_project(root)
        return {
            "path": path.relative_to(root).as_posix(),
            "content": str(content),
            "size": len(encoded),
            "updated_at": utc_now(),
        }

    def list_runs(self, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        root = self.project_path(project_id)
        records: list[dict[str, Any]] = []
        for path in sorted((root / "runs").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            record = self._read_json(path)
            if record:
                records.append(record)
            if len(records) >= max(1, min(int(limit), 200)):
                break
        return records

    def save_run(self, project_id: str, record: dict[str, Any]) -> dict[str, Any]:
        root = self.project_path(project_id)
        run_id = str(record.get("run_id") or f"run_{uuid4().hex[:16]}")
        if not re.fullmatch(r"run_[a-zA-Z0-9_-]{1,80}", run_id):
            raise ValueError("invalid run id")
        payload = {**record, "run_id": run_id, "updated_at": utc_now()}
        payload.setdefault("created_at", payload["updated_at"])
        self._write_json(root / "runs" / f"{run_id}.json", payload)
        self._touch_project(root)
        return payload

    def read_notebook(self, project_id: str) -> dict[str, Any]:
        root = self.project_path(project_id)
        path = root / "notebook" / NOTEBOOK_FILE
        if not path.exists():
            path.write_text("# Research notes\n\n", encoding="utf-8")
        return {"path": f"notebook/{NOTEBOOK_FILE}", "content": path.read_text(encoding="utf-8")}

    def write_notebook(self, project_id: str, content: str) -> dict[str, Any]:
        encoded = str(content).encode("utf-8")
        if len(encoded) > MAX_NOTEBOOK_BYTES:
            raise ValueError("notebook must be 2 MB or smaller")
        root = self.project_path(project_id)
        path = root / "notebook" / NOTEBOOK_FILE
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        self._touch_project(root)
        return {"path": f"notebook/{NOTEBOOK_FILE}", "content": str(content), "updated_at": utc_now()}

    def codex_thread_id(self, project_id: str) -> str | None:
        root = self.project_path(project_id)
        state = self._read_json(root / ".catalyst" / "codex.json") or {}
        value = state.get("thread_id")
        return str(value) if value else None

    def save_codex_state(self, project_id: str, *, thread_id: str, last_response: str) -> None:
        root = self.project_path(project_id)
        self._write_json(root / ".catalyst" / "codex.json", {
            "thread_id": thread_id,
            "last_run_at": utc_now(),
            "last_response": last_response[-20_000:],
        })
        self._touch_project(root)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _touch_project(self, root: Path) -> None:
        metadata = self._read_metadata(root / "project.json")
        if metadata is None:
            return
        metadata["updated_at"] = utc_now()
        self._write_json(root / "project.json", metadata)

    @staticmethod
    def _editable_path(root: Path, relative_path: str) -> Path:
        raw = str(relative_path or "").replace("\\", "/").strip("/")
        if not raw or len(raw) > 240:
            raise ValueError("project path is required and must be 240 characters or fewer")
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in EDITABLE_ROOTS:
            raise ValueError("project files must stay inside files, notebook, or artifacts")
        if relative.suffix.lower() not in EDITABLE_SUFFIXES:
            raise ValueError("unsupported project text file type")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("project file path escapes the project root") from exc
        return path
