install:
	pip install -e .[dev]

run:
	uvicorn weather_platform.main:app --host 0.0.0.0 --port 8000 --reload

ingest:
	.venv/Scripts/python.exe scripts/process_wx_data.py

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(msg)"

up:
	docker compose up --build

down:
	docker compose down -v
