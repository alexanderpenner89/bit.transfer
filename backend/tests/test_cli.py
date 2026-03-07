from unittest.mock import patch, MagicMock, AsyncMock

from typer.testing import CliRunner
from cli import app

runner = CliRunner()


def test_cli_without_args_shows_help():
    result = runner.invoke(app)
    assert result.exit_code == 2
    assert "Usage:" in result.output


def test_generate_with_valid_profile():
    mock_profil = MagicMock()
    mock_profil.gewerk_id = "TEST_01"
    mock_profil.gewerk_name = "Test Gewerk"

    with patch("cli.ProfileParsingAgent") as mock_parser:
        mock_parser.return_value.parse_file.return_value = mock_profil

        result = runner.invoke(app, ["test_profile.json"])

    assert result.exit_code == 0
    assert "TEST_01" in result.output or "Lade Profil" in result.output


def test_generate_calls_orchestrator():
    mock_profil = MagicMock()
    mock_profil.gewerk_id = "A_01_MAURER"
    mock_profil.gewerk_name = "Maurer"
    mock_profil.hwo_anlage = "A"

    mock_strategy = MagicMock()
    mock_strategy.model_dump_json.return_value = '{"gewerk_id": "A_01_MAURER"}'

    with patch("cli.ProfileParsingAgent") as mock_parser, \
         patch("cli.OrchestratorAgent") as mock_orch:
        mock_parser.return_value.parse_file.return_value = mock_profil
        mock_orch_instance = MagicMock()
        mock_orch_instance.generate = AsyncMock(return_value=mock_strategy)
        mock_orch.return_value = mock_orch_instance

        result = runner.invoke(app, ["maurer.json"])

    assert result.exit_code == 0
    mock_orch_instance.generate.assert_called_once()


def test_file_not_found_error():
    result = runner.invoke(app, ["nonexistent.json"])
    assert result.exit_code == 1
    assert "nicht gefunden" in result.output or "not found" in result.output.lower()


def test_verbose_shows_traceback():
    result = runner.invoke(app, ["nonexistent.json", "--verbose"])
    assert result.exit_code == 1
    assert "Traceback" in result.output or "FileNotFoundError" in result.output
