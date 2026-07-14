from fastapi.testclient import TestClient

from catalyst.agent.registry import tool_names
from catalyst.genomics_demo import get_case, repeat_interpretation
from catalyst.local_api import app


def test_genomics_cases_are_curated_and_repeat_bands_are_bounded() -> None:
    brca1 = get_case("brca1")
    assert brca1 is not None
    assert brca1["gene"] == "BRCA1"
    assert len(brca1["sequence_window"]) >= 24
    assert repeat_interpretation(37)["band"] == "normal"
    assert repeat_interpretation(38)["band"] == "pre_mutation"
    assert repeat_interpretation(50)["band"] == "disease_range"
    assert repeat_interpretation(999)["repeat_count"] == 100


def test_genomics_api_and_agent_registry_contract() -> None:
    client = TestClient(app)
    listing = client.get("/genomics/cases")
    assert listing.status_code == 200
    assert [item["case_id"] for item in listing.json()["cases"]] == ["brca1", "hbb", "ctg"]

    ctg = client.get("/genomics/cases/ctg?repeat_count=55")
    assert ctg.status_code == 200
    assert ctg.json()["repeat"]["band"] == "disease_range"
    assert client.get("/genomics/cases/not-a-case").status_code == 404
    assert "inspect_genomics_case" in tool_names()
