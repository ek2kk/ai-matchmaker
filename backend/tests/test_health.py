from ai_dating.app import app_version


def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": app_version()}


def test_healthz_has_request_id(client):
    response = client.get("/healthz")
    assert response.headers["x-request-id"]
