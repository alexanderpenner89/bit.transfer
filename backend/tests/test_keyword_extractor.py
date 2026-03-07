import pytest
from pathlib import Path

from agents.keyword_extractor import KeywordExtractor
from schemas.gewerksprofil import GewerksProfilModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


@pytest.fixture
def maurer_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


@pytest.fixture
def extractor() -> KeywordExtractor:
    return KeywordExtractor()


class TestExtractKeywords:
    def test_returns_at_least_5_queries(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        assert len(queries) >= 5

    def test_all_queries_are_strings(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        assert all(isinstance(q, str) for q in queries)

    def test_queries_contain_boolean_operators(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        has_operator = any("AND" in q or "OR" in q for q in queries)
        assert has_operator, "Mindestens eine Query muss AND oder OR enthalten"

    def test_queries_contain_profile_terms(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        all_terms = " ".join(queries).lower()
        kernkompetenzen_terms = [k.lower() for k in maurer_profil.kernkompetenzen]
        found = any(term in all_terms for term in kernkompetenzen_terms)
        assert found, "Queries müssen Begriffe aus kernkompetenzen enthalten"

    def test_no_llm_dependency(self, extractor, maurer_profil):
        """KeywordExtractor darf keinen pydantic-ai Agent haben."""
        assert not hasattr(extractor, "agent"), "KeywordExtractor darf keinen pydantic-ai Agent haben"

    def test_tischler_profil_also_works(self, extractor):
        text = (PROFILES_DIR / "tischler.json").read_text(encoding="utf-8")
        profil = GewerksProfilModel.model_validate_json(text)
        queries = extractor.extract_keyword_queries(profil)
        assert len(queries) >= 5

    def test_elektrotechniker_profil_also_works(self, extractor):
        text = (PROFILES_DIR / "elektrotechniker.json").read_text(encoding="utf-8")
        profil = GewerksProfilModel.model_validate_json(text)
        queries = extractor.extract_keyword_queries(profil)
        assert len(queries) >= 5


class TestQueryGrouping:
    def test_generates_queries_per_profilfeld(self, extractor, maurer_profil):
        queries_by_field = extractor.extract_queries_by_field(maurer_profil)
        assert "kernkompetenzen" in queries_by_field
        assert "werkstoffe" in queries_by_field
        assert len(queries_by_field["kernkompetenzen"]) >= 1

    def test_combines_related_terms_with_or(self, extractor, maurer_profil):
        queries_by_field = extractor.extract_queries_by_field(maurer_profil)
        all_queries = " ".join(str(v) for v in queries_by_field.values())
        assert "OR" in all_queries
