install:
	pip install -e .[dev]

run:
	uvicorn weather_platform.main:app --reload

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
