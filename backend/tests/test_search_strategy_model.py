import pytest
from pydantic import ValidationError

from schemas.search_strategy import ForschungsFrage, SearchStrategyModel


class TestForschungsFrageModel:
    def test_valid_frage_creates_model(self):
        frage = ForschungsFrage(
            frage="Welche ergonomischen Risiken bestehen beim Mauern?",
            bezug_profilfelder=["arbeitsbedingungen", "techniken_manuell"],
            prioritaet=1,
        )
        assert frage.frage == "Welche ergonomischen Risiken bestehen beim Mauern?"
        assert "arbeitsbedingungen" in frage.bezug_profilfelder

    def test_prioritaet_must_be_1_to_3(self):
        with pytest.raises(ValidationError):
            ForschungsFrage(
                frage="Test",
                bezug_profilfelder=["kernkompetenzen"],
                prioritaet=0,
            )

    def test_bezug_profilfelder_min_one(self):
        with pytest.raises(ValidationError):
            ForschungsFrage(
                frage="Test",
                bezug_profilfelder=[],
                prioritaet=1,
            )

    def test_prioritaet_above_max_raises(self):
        with pytest.raises(ValidationError):
            ForschungsFrage(
                frage="Test",
                bezug_profilfelder=["kernkompetenzen"],
                prioritaet=4,
            )

    def test_prioritaet_valid_boundaries(self):
        # Both extremes must be valid
        ForschungsFrage(frage="Test", bezug_profilfelder=["x"], prioritaet=1)
        ForschungsFrage(frage="Test", bezug_profilfelder=["x"], prioritaet=3)


class TestSearchStrategyModel:
    def test_valid_model_creates_correctly(self):
        strategy = SearchStrategyModel(
            gewerk_id="A_01_MAURER",
            forschungsfragen=[
                ForschungsFrage(frage="Welche Materialien optimieren Mauerwerk?", bezug_profilfelder=["werkstoffe"], prioritaet=1),
                ForschungsFrage(frage="Welche Techniken reduzieren Rückenbelastung?", bezug_profilfelder=["arbeitsbedingungen"], prioritaet=2),
                ForschungsFrage(frage="Wie wirken sich neue Baustoffe auf Haftung aus?", bezug_profilfelder=["werkstoffe", "techniken_manuell"], prioritaet=3),
            ],
            keyword_queries_de=["Mauerwerk AND Ziegel", "Beton AND Bewehrung"],
            keyword_queries_en=["masonry AND brick", "concrete AND reinforcement"],
            semantic_queries_en=["load-bearing masonry construction techniques"],
            hyde_abstracts=[],
            concept_filter_ids=None,
            max_results_per_query=50,
        )
        assert strategy.gewerk_id == "A_01_MAURER"
        assert len(strategy.forschungsfragen) == 3
        assert len(strategy.keyword_queries_de) >= 1

    def test_forschungsfragen_min_3_required(self):
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage="F1", bezug_profilfelder=["x"], prioritaet=1),
                    ForschungsFrage(frage="F2", bezug_profilfelder=["y"], prioritaet=2),
                ],
                keyword_queries_de=["a"],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
                max_results_per_query=50,
            )

    def test_max_results_default_is_50(self):
        strategy = SearchStrategyModel(
            gewerk_id="TEST",
            forschungsfragen=[
                ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                for i in range(3)
            ],
            keyword_queries_de=["a"],
            keyword_queries_en=["b"],
            semantic_queries_en=["c"],
            hyde_abstracts=[],
            concept_filter_ids=None,
        )
        assert strategy.max_results_per_query == 50

    def test_keyword_queries_de_min_one(self):
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                    for i in range(3)
                ],
                keyword_queries_de=[],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
            )

    def test_forschungsfragen_max_10_enforced(self):
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                    for i in range(11)
                ],
                keyword_queries_de=["a"],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
            )

    def test_max_results_upper_bound_enforced(self):
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                    for i in range(3)
                ],
                keyword_queries_de=["a"],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
                max_results_per_query=201,
            )
