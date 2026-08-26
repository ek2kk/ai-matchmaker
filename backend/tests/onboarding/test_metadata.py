from fastapi.testclient import TestClient

from tests.onboarding.helpers import account, auth_of


def test_metadata_returns_versioned_vocab(client: TestClient):
    acc = account(client)
    response = client.get("/v1/metadata/onboarding", headers=auth_of(acc))
    assert response.status_code == 200
    body = response.json()
    assert body["flow_version"] == "v2"
    codes = {item["code"] for item in body["genders"]}
    assert codes == {"man", "woman"}
    assert {item["code"] for item in body["search_modes"]} == {"dating", "friendship"}
    assert {item["code"] for item in body["prompts"]} >= {
        "self_about",
        "partner_who",
    }
    assert body["orientations"][0]["code"] == "heterosexual"
    assert "policy_version" in body
