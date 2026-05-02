from decimal import Decimal

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat


def test_post_and_get_observation_round_trip(client, db_session) -> None:
    """POST /observations should persist data that GET /observations/{station_id}/{date} returns."""
    payload = {
        "station_id": "USC00110072",
        "observation_date": "2024-04-30",
        "max_temp_c": "25.5",
        "min_temp_c": "12.0",
        "precipitation_cm": "0.2",
        "source_file": "sample.txt",
    }

    create_response = client.post("/api/v1/weather/observations", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["station_id"] == payload["station_id"]
    assert created["observation_date"] == payload["observation_date"]

    get_response = client.get("/api/v1/weather/observations/USC00110072/2024-04-30")
    assert get_response.status_code == 200
    retrieved = get_response.json()
    assert retrieved["station_id"] == payload["station_id"]
    assert Decimal(retrieved["max_temp_c"]) == Decimal(payload["max_temp_c"])
    assert Decimal(retrieved["min_temp_c"]) == Decimal(payload["min_temp_c"])
    assert Decimal(retrieved["precipitation_cm"]) == Decimal(payload["precipitation_cm"])

    persisted = db_session.query(WeatherObservation).count()
    assert persisted == 1


def test_observation_query_endpoint_paginates_and_filters(client, db_session) -> None:
    """GET /observations should honor skip, limit, station, and date filters."""
    records = [
        {
            "station_id": "USC00110072",
            "observation_date": "2024-04-28",
            "max_temp_c": "23.0",
            "min_temp_c": "11.0",
            "precipitation_cm": "0.0",
        },
        {
            "station_id": "USC00110072",
            "observation_date": "2024-04-29",
            "max_temp_c": "24.0",
            "min_temp_c": "12.0",
            "precipitation_cm": "0.1",
        },
        {
            "station_id": "USC00110072",
            "observation_date": "2024-04-30",
            "max_temp_c": None,
            "min_temp_c": "13.0",
            "precipitation_cm": None,
        },
        {
            "station_id": "USC00250070",
            "observation_date": "2024-04-30",
            "max_temp_c": "21.0",
            "min_temp_c": "9.0",
            "precipitation_cm": "0.4",
        },
    ]

    for record in records:
        response = client.post("/api/v1/weather/observations", json=record)
        assert response.status_code == 201

    response = client.get(
        "/api/v1/weather/observations",
        params={
            "station_id": "USC00110072",
            "start_date": "2024-04-29",
            "end_date": "2024-04-30",
            "skip": 0,
            "limit": 1,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 2
    assert payload["skip"] == 0
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["observation_date"] == "2024-04-30"

    next_page = client.get(
        "/api/v1/weather/observations",
        params={
            "station_id": "USC00110072",
            "start_date": "2024-04-29",
            "end_date": "2024-04-30",
            "skip": 1,
            "limit": 1,
        },
    )
    assert next_page.status_code == 200
    assert next_page.json()["items"][0]["observation_date"] == "2024-04-29"


def test_yearly_stats_endpoint_returns_paginated_results(client, db_session) -> None:
    """GET /stats should filter and paginate yearly statistics."""
    stats = [
        WeatherYearlyStat(
            id=1,
            station_id="USC00110072",
            year=2022,
            avg_max_temp_c=Decimal("24.0"),
            avg_min_temp_c=Decimal("12.0"),
            total_precipitation_cm=Decimal("100.0"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            id=2,
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("25.0"),
            avg_min_temp_c=Decimal("13.0"),
            total_precipitation_cm=Decimal("110.0"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            id=3,
            station_id="USC00250070",
            year=2023,
            avg_max_temp_c=Decimal("21.0"),
            avg_min_temp_c=Decimal("9.0"),
            total_precipitation_cm=Decimal("90.0"),
            observation_count=365,
        ),
    ]
    db_session.add_all(stats)
    db_session.commit()

    response = client.get(
        "/api/v1/weather/stats",
        params={
            "station_id": "USC00110072",
            "start_year": 2022,
            "end_year": 2023,
            "skip": 0,
            "limit": 1,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 2
    assert payload["skip"] == 0
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["year"] == 2023

    next_page = client.get(
        "/api/v1/weather/stats",
        params={
            "station_id": "USC00110072",
            "start_year": 2022,
            "end_year": 2023,
            "skip": 1,
            "limit": 1,
        },
    )
    assert next_page.status_code == 200
    assert next_page.json()["items"][0]["year"] == 2022
