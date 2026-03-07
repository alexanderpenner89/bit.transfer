import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.profile_parser import ProfileParsingAgent
from schemas.gewerksprofil import GewerksProfilModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


@pytest.fixture
def agent():
    return ProfileParsingAgent()


@pytest.fixture
def valid_maurer_json():
    return (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")


class TestParseString:
    def test_valid_profile_returns_model(self, agent, valid_maurer_json):
        result = agent.parse_string(valid_maurer_json)
        assert isinstance(result, GewerksProfilModel)
        assert result.gewerk_id == "A_01_MAURER"

    def test_missing_required_field_raises_validation_error(self, agent):
        invalid = json.dumps({"gewerk_id": "X_01_TEST"})
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(invalid)
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "gewerk_name" in error_fields

    def test_wrong_hwo_anlage_value_raises_validation_error(self, agent, valid_maurer_json):
        data = json.loads(valid_maurer_json)
        data["hwo_anlage"] = "C"
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(json.dumps(data))
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "hwo_anlage" in error_fields

    def test_empty_list_field_raises_validation_error(self, agent, valid_maurer_json):
        data = json.loads(valid_maurer_json)
        data["kernkompetenzen"] = []
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(json.dumps(data))
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "kernkompetenzen" in error_fields

    def test_invalid_json_raises_validation_error(self, agent):
        with pytest.raises(ValidationError):
            agent.parse_string("{not valid json}")


class TestParseFile:
    def test_loads_maurer_profile(self, agent):
        path = PROFILES_DIR / "maurer.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_01_MAURER"

    def test_loads_tischler_profile(self, agent):
        path = PROFILES_DIR / "tischler.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_13_TISCHLER"

    def test_loads_elektrotechniker_profile(self, agent):
        path = PROFILES_DIR / "elektrotechniker.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_09_ELEKTROTECHNIKER"

    def test_nonexistent_file_raises_file_not_found(self, agent):
        with pytest.raises(FileNotFoundError):
            agent.parse_file("/nonexistent/path/profile.json")

    def test_accepts_string_path(self, agent):
        path = str(PROFILES_DIR / "maurer.json")
        result = agent.parse_file(path)
        assert isinstance(result, GewerksProfilModel)


class TestPerformance:
    def test_100_parses_under_100ms(self, agent, valid_maurer_json):
        start = time.perf_counter()
        for _ in range(100):
            agent.parse_string(valid_maurer_json)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"100 parses took {elapsed_ms:.1f}ms, expected <100ms"
