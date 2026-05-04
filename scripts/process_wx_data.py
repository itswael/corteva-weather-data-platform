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
import logging
import os
from datetime import datetime


def main():
    data_dir = ROOT / "wx_data"
    if not data_dir.exists():
        print(f"wx_data directory not found at {data_dir}")
        return
    
    # ensure logs directory exists and configure logging
    logs_dir = ROOT / "logs"
    try:
        logs_dir.mkdir(exist_ok=True)
    except Exception:
        pass

    log_file = logs_dir / "ingestion.log"
    logger = logging.getLogger("weather_ingest")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(sh)
        logger.addHandler(fh)
    session = SessionLocal()
    try:
        repository = SQLAlchemyWeatherRepository(session)
        service = WeatherService(repository)
        parser = WeatherStationTextFileParser()
        ingestor = WeatherFileIngestor(service=service, parser=parser)

        total_processed = 0
        total_inserted = 0
        start_time = datetime.utcnow()
        logger.info("Ingestion started: wx_data=%s", str(data_dir))
        files = sorted([p for p in data_dir.iterdir() if p.suffix.lower() == ".txt"])
        if not files:
            logger.info("No .txt files found in wx_data")
            return

        for f in files:
            try:
                summary = ingestor.ingest_file(f)
                logger.info("Processed %s: processed=%d inserted=%d skipped=%d", f.name, summary.processed, summary.inserted, summary.skipped_duplicates)
                total_processed += summary.processed
                total_inserted += summary.inserted
            except Exception as exc:
                logger.exception("Failed to process %s", f.name)

        end_time = datetime.utcnow()
        duration = end_time - start_time
        logger.info("Summary: files=%d total_processed=%d total_inserted=%d duration=%s", len(files), total_processed, total_inserted, str(duration))
    finally:
        session.close()
        logger.info("Session closed")


if __name__ == "__main__":
    main()
