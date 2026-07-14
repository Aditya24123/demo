from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from catalyst import local_api
from catalyst.project_store import ProjectStore, sanitize_project_id


def test_project_id_sanitization_and_store_containment(tmp_path: Path) -> None:
    assert sanitize_project_id("Battery / Oxides") == "battery-oxides"
    assert sanitize_project_id("../outside") == "outside"

    store = ProjectStore(tmp_path)
    project = store.create_project(name="Battery / Oxides", description="Local project")
    assert project["project_id"] == "battery-oxides"
    assert (tmp_path / "data" / "workspaces" / "battery-oxides" / "files").is_dir()
    assert (tmp_path / "data" / "workspaces" / "battery-oxides" / "notebook" / "research.md").is_file()
    escaped = store.create_project(name="Escaped input", project_id="../../escape")
    assert escaped["project_id"] == "escape"
    assert (tmp_path / "data" / "workspaces" / "escape").is_dir()
    assert not (tmp_path / "escape").exists()
    outside = store.create_project(name="Outside")
    assert outside["project_id"] == "outside"
    try:
        store.get_project("../outside")
    except ValueError as exc:
        assert "project_id" in str(exc)
    else:
        raise AssertionError("unsafe lookup must be rejected instead of resolving another project")

    try:
        store.create_project(name="Too much", description="x" * 501)
    except ValueError as exc:
        assert "description" in str(exc)
    else:
        raise AssertionError("oversized descriptions must be rejected")


def test_project_api_persists_create_update_and_archive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_api, "_repo_root", lambda: tmp_path)
    local_api.get_projects.cache_clear()
    client = TestClient(local_api.app)

    created = client.post("/projects", json={"name": "Graph review", "description": "First pass"})
    assert created.status_code == 201
    project = created.json()
    assert project["project_id"] == "graph-review"
    assert project["archived"] is False

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert [item["project_id"] for item in listed.json()["projects"]] == ["graph-review"]

    updated = client.patch(f"/projects/{project['project_id']}", json={"name": "Graph review v2"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Graph review v2"

    archived = client.post(f"/projects/{project['project_id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert client.get("/projects").json()["projects"] == []
    assert client.get("/projects?include_archived=true").json()["projects"][0]["archived"] is True

    outside = client.get("/projects/%2e%2e%2foutside")
    assert outside.status_code in {400, 404}


def test_project_workspace_and_notebook_are_real_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_api, "_repo_root", lambda: tmp_path)
    local_api.get_projects.cache_clear()
    client = TestClient(local_api.app)

    created = client.post("/projects", json={"name": "Solid state notebook"}).json()
    project_id = created["project_id"]

    notebook = client.get(f"/projects/{project_id}/notebook")
    assert notebook.status_code == 200
    assert notebook.json()["content"].startswith("# Solid state notebook")

    updated = client.put(
        f"/projects/{project_id}/notebook",
        json={"content": "# Experiment 01\n\nObserved stable phase."},
    )
    assert updated.status_code == 200
    notebook_path = tmp_path / "data" / "workspaces" / project_id / "notebook" / "research.md"
    assert notebook_path.read_text(encoding="utf-8") == "# Experiment 01\n\nObserved stable phase."

    workspace = client.get(f"/projects/{project_id}/workspace")
    assert workspace.status_code == 200
    assert "notebook" in workspace.json()["folders"]
    assert any(item["path"] == "notebook/research.md" for item in workspace.json()["files"])
    assert workspace.json()["codex"]["runtime"]["available"] is False

    oversized = client.put(f"/projects/{project_id}/notebook", json={"content": "x" * (2 * 1024 * 1024 + 1)})
    assert oversized.status_code == 400

    written = client.put(
        f"/projects/{project_id}/files/artifacts/summary.json",
        json={"content": '{"stable": true}'},
    )
    assert written.status_code == 200
    assert written.json()["path"] == "artifacts/summary.json"
    read_back = client.get(f"/projects/{project_id}/files/artifacts/summary.json")
    assert read_back.json()["content"] == '{"stable": true}'

    escaped = client.put(
        f"/projects/{project_id}/files/%2e%2e/project.json",
        json={"content": "no"},
    )
    assert escaped.status_code in {400, 404}
    unsupported = client.put(
        f"/projects/{project_id}/files/files/binary.exe",
        json={"content": "no"},
    )
    assert unsupported.status_code == 400

    run = local_api.get_projects().save_run(project_id, {"kind": "test", "status": "completed"})
    runs = client.get(f"/projects/{project_id}/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == run["run_id"]
