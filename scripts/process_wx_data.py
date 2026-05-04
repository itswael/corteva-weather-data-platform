"""Process all weather files in wx_data using the app's ingestion code.

Run with the project's virtualenv python from repository root:

    .venv\Scripts\python.exe scripts\process_wx_data.py

This script inserts `src` into sys.path so imports work from the repo layout.
"""
import sys
from pathlib import Path

# ensure package imports work (src is the package root)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_platform.ingestion.ingest_weather_file import WeatherFileIngestor, WeatherStationTextFileParser
from weather_platform.services.weather import WeatherService
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.config.database import SessionLocal


def main():
    data_dir = ROOT / "wx_data"
    if not data_dir.exists():
        print(f"wx_data directory not found at {data_dir}")
        return

    session = SessionLocal()
    try:
        repository = SQLAlchemyWeatherRepository(session)
        service = WeatherService(repository)
        parser = WeatherStationTextFileParser()
        ingestor = WeatherFileIngestor(service=service, parser=parser)

        total_processed = 0
        total_inserted = 0
        files = sorted([p for p in data_dir.iterdir() if p.suffix.lower() == ".txt"])
        if not files:
            print("No .txt files found in wx_data")
            return

        for f in files:
            try:
                summary = ingestor.ingest_file(f)
                print(f"Processed {f.name}: processed={summary.processed}, inserted={summary.inserted}, skipped={summary.skipped_duplicates}")
                total_processed += summary.processed
                total_inserted += summary.inserted
            except Exception as exc:
                print(f"Failed to process {f.name}: {exc}")

        print(f"\nSummary: files={len(files)}, total_processed={total_processed}, total_inserted={total_inserted}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
