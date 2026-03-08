"""End-to-End Tests für CLI mit gemocktem LLM."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from typer.testing import CliRunner
from cli import app

runner = CliRunner()


def test_e2e_full_workflow():
    """Testet den vollständigen Workflow mit gemocktem Orchestrator."""
    # Temporäre Profil-Datei erstellen
    profile_data = {
        "gewerk_id": "TEST_01",
        "gewerk_name": "Test Gewerk",
        "hwo_anlage": "A",
        "kernkompetenzen": ["Testen"],
        "taetigkeitsfelder": {"Herstellung": ["Test machen"]},
        "techniken_manuell": ["Handtest"],
        "techniken_maschinell": ["Maschinentest"],
        "techniken_oberflaeche": ["Oberflächentest"],
        "werkstoffe": ["Testmaterial"],
        "software_tools": ["TestTool"],
        "arbeitsbedingungen": ["Testbedingungen"]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(profile_data, f)
        profile_path = f.name

    try:
        # Mock-Strategie erstellen
        mock_strategy = MagicMock()
        mock_strategy.gewerk_id = "TEST_01"
        mock_strategy.forschungsfragen = []
        mock_strategy.keyword_queries_de = ["Test AND Query"]
        mock_strategy.keyword_queries_en = ["Test AND Query"]
        mock_strategy.semantic_queries_en = ["Test query description"]
        mock_strategy.model_dump_json.return_value = json.dumps({
            "gewerk_id": "TEST_01",
            "forschungsfragen": [],
            "keyword_queries_de": ["Test AND Query"],
            "keyword_queries_en": ["Test AND Query"],
            "semantic_queries_en": ["Test query description"]
        })

        with patch("cli.OrchestratorAgent") as mock_orch_class:
            mock_orch = MagicMock()
            mock_orch.generate = AsyncMock(return_value=mock_strategy)
            mock_orch_class.return_value = mock_orch

            result = runner.invoke(app, ["generate", profile_path])

        assert result.exit_code == 0
        assert "Strategie generiert" in result.output

    finally:
        Path(profile_path).unlink()


def test_e2e_with_output_file():
    """Testet das Speichern in eine Datei."""
    profile_data = {
        "gewerk_id": "TEST_02",
        "gewerk_name": "Test Gewerk 2",
        "hwo_anlage": "A",
        "kernkompetenzen": ["Testen"],
        "taetigkeitsfelder": {},
        "techniken_manuell": ["Handtest"],
        "techniken_maschinell": ["Maschinentest"],
        "techniken_oberflaeche": ["Oberflächentest"],
        "werkstoffe": ["Testmaterial"],
        "software_tools": ["TestTool"],
        "arbeitsbedingungen": ["Testbedingungen"]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(profile_data, f)
        profile_path = f.name

    output_path = profile_path.replace(".json", "_output.json")

    try:
        mock_strategy = MagicMock()
        mock_strategy.model_dump_json.return_value = '{"test": true}'

        with patch("cli.OrchestratorAgent") as mock_orch_class:
            mock_orch = MagicMock()
            mock_orch.generate = AsyncMock(return_value=mock_strategy)
            mock_orch_class.return_value = mock_orch

            result = runner.invoke(app, ["generate", profile_path, "--output", output_path])

        assert result.exit_code == 0
        assert Path(output_path).exists()
        assert "Gespeichert nach" in result.output

    finally:
        Path(profile_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)
