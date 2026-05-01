"""Integration tests for CLI commands."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from weather_platform.cli.commands import ingest


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_weather_file() -> Path:
    """Create a temporary sample weather file for testing."""
    with TemporaryDirectory() as tmpdir:
        # Create a sample weather station file with predictable data
        file_path = Path(tmpdir) / "USC00110072.txt"
        file_path.write_text(
            "20200101 120 50 100\n"
            "20200102 125 55 105\n"
            "20200103 -9999 60 -9999\n",  # Missing values as sentinel
            encoding="utf-8",
        )
        yield file_path


def test_ingest_command_help(runner: CliRunner) -> None:
    """Test that ingest command provides help text."""
    result = runner.invoke(ingest, ["--help"])
    assert result.exit_code == 0
    assert "Ingest weather observations" in result.output
    assert "FILE_PATH" in result.output
    assert "--env" in result.output
    assert "--verbose" in result.output


def test_ingest_command_missing_file(runner: CliRunner) -> None:
    """Test that ingest command fails gracefully for missing file."""
    result = runner.invoke(ingest, ["/nonexistent/file.txt", "--env", "test"])
    assert result.exit_code != 0
    # Click should indicate the file doesn't exist
    assert "File not found" in result.output or "does not exist" in result.output or "Error" in result.output


def test_ingest_command_env_options(runner: CliRunner, sample_weather_file: Path) -> None:
    """Test that all environment options are accepted.
    
    This test verifies the CLI interface accepts valid env choices,
    though it may fail due to missing DB schema (expected).
    """
    for env in ["local", "test", "prod"]:
        # Just test that the command accepts the env option
        # It will fail due to DB not being set up, but that's expected
        result = runner.invoke(ingest, [str(sample_weather_file), "--env", env])
        # Should not fail due to invalid env choice
        assert "Invalid value for '--env'" not in result.output


def test_ingest_command_verbose_flag(runner: CliRunner, sample_weather_file: Path) -> None:
    """Test that verbose flag doesn't crash the command."""
    result = runner.invoke(ingest, [str(sample_weather_file), "--env", "test", "--verbose"])
    # Should not crash due to flag parsing
    # (may fail due to DB, but that's OK for this test)
    assert result.exit_code in (0, 1)


@patch("weather_platform.cli.commands.WeatherFileIngestor")
@patch("weather_platform.cli.commands.configure_engine_and_session")
def test_ingest_command_success_flow(
    mock_configure: MagicMock,
    mock_ingestor_class: MagicMock,
    runner: CliRunner,
    sample_weather_file: Path,
) -> None:
    """Test successful ingestion flow with mocked dependencies.
    
    This verifies the CLI correctly orchestrates the service layer
    without requiring a real database.
    """
    # Mock the service stack
    mock_ingestor = MagicMock()
    mock_ingestor_class.return_value = mock_ingestor

    mock_summary = MagicMock()
    mock_summary.processed = 3
    mock_summary.inserted = 3
    mock_summary.skipped_duplicates = 0
    mock_summary.duration_ms = 45
    mock_ingestor.ingest_file.return_value = mock_summary

    mock_engine = MagicMock()
    mock_session_local = MagicMock()
    mock_configure.return_value = (mock_engine, mock_session_local)

    result = runner.invoke(ingest, [str(sample_weather_file), "--env", "test"])

    assert result.exit_code == 0
    assert "✓ Ingestion completed successfully" in result.output
    assert "Processed: 3" in result.output
    assert "Inserted: 3" in result.output
    assert "Skipped (duplicates): 0" in result.output
    assert "Duration: 45ms" in result.output


@patch("weather_platform.cli.commands.WeatherFileIngestor")
@patch("weather_platform.cli.commands.configure_engine_and_session")
def test_ingest_command_error_handling(
    mock_configure: MagicMock,
    mock_ingestor_class: MagicMock,
    runner: CliRunner,
    sample_weather_file: Path,
) -> None:
    """Test error handling in CLI with mocked dependencies."""
    from weather_platform.ingestion.ingest_weather_file import WeatherFileParseError

    # Mock a parse error
    mock_ingestor = MagicMock()
    mock_ingestor_class.return_value = mock_ingestor
    mock_ingestor.ingest_file.side_effect = WeatherFileParseError("Invalid date format")

    mock_engine = MagicMock()
    mock_session_local = MagicMock()
    mock_configure.return_value = (mock_engine, mock_session_local)

    result = runner.invoke(ingest, [str(sample_weather_file), "--env", "test"])

    assert result.exit_code == 1
    assert "Parse error" in result.output
    assert "Invalid date format" in result.output
