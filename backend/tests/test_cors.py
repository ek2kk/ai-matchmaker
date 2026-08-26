def test_cors_allows_local_origin(client):
    response = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_cors_omits_unknown_origin(client):
    response = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"
