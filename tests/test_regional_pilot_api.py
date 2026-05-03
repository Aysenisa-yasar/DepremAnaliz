import pytest


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_regional_pilot_map_returns_json(client):
    response = client.get("/api/v2/regional-pilot-map")
    assert response.status_code == 200

    data = response.get_json()
    assert data is not None
    assert "status" in data
    assert "nodes" in data


def test_home_contains_comparison_panel(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "comparisonStatus" in body
    assert "Hybrid forecast vs province graph-temporal pilot" in body
