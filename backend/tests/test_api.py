from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommend_matched_and_metadata_survives():
    # HK-42352 (Алматы, Ведущий, той, price 900000, price_imputed=True) is the
    # only free "той" host in Алматы on 2026-12-31 per the dataset.
    payload = {
        "city": "Алматы",
        "event_date": "2026-12-31",
        "event_format": "той",
        "category": "Ведущий",
        "budget_kzt": 900_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "MATCHED"
    assert [c["id"] for c in body["results"]] == ["HK-42352"]
    card = body["results"][0]
    assert card["price_imputed"] is True
    assert card["synthetic"] is False
    assert card["city_imputed"] is False


def test_category_absent():
    payload = {
        "city": "Астана",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ресторан",
        "budget_kzt": 10_000_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "CATEGORY_ABSENT"
    assert body["results"] == []


def test_no_match_due_to_budget():
    payload = {
        "city": "Алматы",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 100_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "NO_MATCH"
    assert body["results"] == []
    assert len(body["rejected"]) > 0


def test_category_absent_and_no_match_are_distinguishable():
    absent_payload = {
        "city": "Астана",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ресторан",
        "budget_kzt": 10_000_000,
    }
    no_match_payload = {
        "city": "Алматы",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 100_000,
    }

    absent_status = client.post("/api/v1/recommend", json=absent_payload).json()["status"]
    no_match_status = client.post("/api/v1/recommend", json=no_match_payload).json()["status"]

    assert absent_status == "CATEGORY_ABSENT"
    assert no_match_status == "NO_MATCH"
    assert absent_status != no_match_status


def test_invalid_date_outside_calendar_window_is_rejected():
    payload = {
        "city": "Алматы",
        "event_date": "2027-06-15",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 10_000_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 422
    assert "calendar" in response.json()["detail"].lower()


def test_result_never_exceeds_three():
    payload = {
        "city": "Алматы",
        "event_date": "2026-11-15",
        "event_format": "свадьба",
        "category": "Ведущий",
        "budget_kzt": 10_000_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 3


def test_semantic_score_absent_without_preferences():
    payload = {
        "city": "Алматы",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 700_000,
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "MATCHED"
    assert body["results"]
    assert all(card["semantic_score"] is None for card in body["results"])


def test_preferences_change_ranking_of_the_same_eligible_pool():
    base_payload = {
        "city": "Алматы",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 700_000,
    }
    business_style = client.post(
        "/api/v1/recommend",
        json={
            **base_payload,
            "preferences": "спокойная деловая интеллигентная подача, корпоративный стиль",
        },
    ).json()
    dance_entertainment = client.post(
        "/api/v1/recommend",
        json={**base_payload, "preferences": "яркое шоу с танцами и развлечениями"},
    ).json()

    assert business_style["status"] == dance_entertainment["status"] == "MATCHED"

    business_ids = {c["id"] for c in business_style["results"]}
    dance_ids = {c["id"] for c in dance_entertainment["results"]}
    assert business_ids == dance_ids  # same eligible pool

    for card in business_style["results"] + dance_entertainment["results"]:
        assert card["semantic_score"] is not None

    # Different preferences reorder the same pool.
    assert business_style["results"][0]["id"] != dance_entertainment["results"][0]["id"]


def test_repeated_identical_preferences_return_identical_order_via_api():
    payload = {
        "city": "Алматы",
        "event_date": "2026-10-10",
        "event_format": "корпоратив",
        "category": "Ведущий",
        "budget_kzt": 700_000,
        "preferences": "спокойная деловая интеллигентная подача",
    }
    first = client.post("/api/v1/recommend", json=payload).json()
    second = client.post("/api/v1/recommend", json=payload).json()

    assert [c["id"] for c in first["results"]] == [c["id"] for c in second["results"]]
    assert [c["semantic_score"] for c in first["results"]] == [
        c["semantic_score"] for c in second["results"]
    ]
