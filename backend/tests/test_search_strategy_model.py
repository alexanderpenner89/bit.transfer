import pytest
from pydantic import ValidationError

from schemas.search_strategy import SearchStrategyModel


class TestSearchStrategyModel:
    def _valid_data(self) -> dict:
        return {
            "gewerk_id": "A_01_MAURER",
            "semantic_queries_en": [
                "Load-bearing masonry construction techniques focus on the structural performance "
                "of brick and mortar assemblies in residential and commercial buildings."
            ],
            "boolean_queries_de": [
                '("Mauerwerk" OR "Ziegel" OR "Kalksandstein") AND "Tragfähigkeit"',
                '("Mörtel" OR "Dünnbettmörtel") AND Verarbeitung',
            ],
            "boolean_queries_en": [
                '("masonry" OR "brickwork") AND "structural performance"',
                '("mortar" OR "adhesive mortar") AND application',
            ],
        }

    def test_valid_model_requires_3_fields_only(self):
        strategy = SearchStrategyModel(**self._valid_data())
        assert strategy.gewerk_id == "A_01_MAURER"
        assert len(strategy.semantic_queries_en) == 1
        assert len(strategy.boolean_queries_de) == 2
        assert len(strategy.boolean_queries_en) == 2

    def test_gewerk_id_required(self):
        data = self._valid_data()
        del data["gewerk_id"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_semantic_queries_en_min_1(self):
        data = self._valid_data()
        data["semantic_queries_en"] = []
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_semantic_queries_en_max_2(self):
        data = self._valid_data()
        data["semantic_queries_en"] = ["query one", "query two", "query three"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_boolean_queries_de_min_2(self):
        data = self._valid_data()
        data["boolean_queries_de"] = ["only one query"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_boolean_queries_de_max_3(self):
        data = self._valid_data()
        data["boolean_queries_de"] = ["q1", "q2", "q3", "q4"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_boolean_queries_en_min_2(self):
        data = self._valid_data()
        data["boolean_queries_en"] = ["only one query"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)

    def test_boolean_queries_en_max_3(self):
        data = self._valid_data()
        data["boolean_queries_en"] = ["q1", "q2", "q3", "q4"]
        with pytest.raises(ValidationError):
            SearchStrategyModel(**data)
