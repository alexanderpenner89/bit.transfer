"""Tests for TopicEvaluatorAgent — all mocked, no real API calls."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.evaluator import TopicEvaluatorAgent
from schemas.gewerksprofil import GewerksProfilModel
from schemas.research_pipeline import TopicCandidate, TopicEvaluation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def maurer_profil() -> GewerksProfilModel:
    return GewerksProfilModel(
        gewerk_id="A_01_MAURER",
        gewerk_name="Maurer und Betonbauer",
        hwo_anlage="A",
        kernkompetenzen=["Mauerwerksbau", "Betonbau", "Fassadenbau"],
        taetigkeitsfelder={"Herstellung": ["Mauern", "Betonieren"]},
        techniken_manuell=["Stemmen", "Verzapfen"],
        techniken_maschinell=["Bohren", "Sägen"],
        techniken_oberflaeche=["Verputzen"],
        werkstoffe=["Ziegel", "Beton", "Mörtel"],
        software_tools=["AutoCAD"],
        arbeitsbedingungen=["Freiluftarbeit"],
    )


@pytest.fixture
def relevant_candidate() -> TopicCandidate:
    return TopicCandidate(
        topic_id="T10116",
        display_name="Masonry Construction and Structural Performance",
        frequency=5,
    )


@pytest.fixture
def irrelevant_candidate() -> TopicCandidate:
    return TopicCandidate(
        topic_id="T99999",
        display_name="Quantum Chromodynamics",
        frequency=1,
    )


def _make_mock_result(evaluation: TopicEvaluation):
    mock = MagicMock()
    mock.output = evaluation
    return mock


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------

class TestTopicEvaluatorAgentInit:
    def test_creates_with_default_model(self):
        agent = TopicEvaluatorAgent()
        assert agent is not None

    def test_creates_with_custom_model(self):
        agent = TopicEvaluatorAgent(model="openai:gpt-4o")
        assert agent is not None

    def test_has_pydantic_ai_agent(self):
        from pydantic_ai import Agent
        agent = TopicEvaluatorAgent()
        assert isinstance(agent.agent, Agent)


# ---------------------------------------------------------------------------
# evaluate() tests
# ---------------------------------------------------------------------------

class TestTopicEvaluatorEvaluate:
    def test_returns_topic_evaluation(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        mock_result = _make_mock_result(
            TopicEvaluation(
                topic_id="T10116",
                display_name="Masonry Construction and Structural Performance",
                is_relevant=True,
                reasoning="Directly related to masonry trade.",
                confidence=0.95,
            )
        )
        with patch.object(agent.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(agent.evaluate(relevant_candidate, maurer_profil))

        assert isinstance(result, TopicEvaluation)

    def test_relevant_topic_flagged(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        mock_result = _make_mock_result(
            TopicEvaluation(
                topic_id="T10116",
                display_name="Masonry Construction and Structural Performance",
                is_relevant=True,
                reasoning="Directly relevant.",
                confidence=0.9,
            )
        )
        with patch.object(agent.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(agent.evaluate(relevant_candidate, maurer_profil))

        assert result.is_relevant is True

    def test_irrelevant_topic_flagged(self, maurer_profil, irrelevant_candidate):
        agent = TopicEvaluatorAgent()
        mock_result = _make_mock_result(
            TopicEvaluation(
                topic_id="T99999",
                display_name="Quantum Chromodynamics",
                is_relevant=False,
                reasoning="Not applicable to masonry trade.",
                confidence=0.99,
            )
        )
        with patch.object(agent.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(agent.evaluate(irrelevant_candidate, maurer_profil))

        assert result.is_relevant is False

    def test_result_has_reasoning(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        mock_result = _make_mock_result(
            TopicEvaluation(
                topic_id="T10116",
                display_name="Masonry Construction and Structural Performance",
                is_relevant=True,
                reasoning="Has clear applied relevance.",
                confidence=0.85,
            )
        )
        with patch.object(agent.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(agent.evaluate(relevant_candidate, maurer_profil))

        assert len(result.reasoning) > 0

    def test_confidence_in_valid_range(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        mock_result = _make_mock_result(
            TopicEvaluation(
                topic_id="T10116",
                display_name="Masonry Construction and Structural Performance",
                is_relevant=True,
                reasoning="Relevant.",
                confidence=0.85,
            )
        )
        with patch.object(agent.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(agent.evaluate(relevant_candidate, maurer_profil))

        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# User prompt tests
# ---------------------------------------------------------------------------

class TestUserPrompt:
    def test_prompt_contains_topic_name(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        prompt = agent._build_user_prompt(relevant_candidate, maurer_profil)
        assert "Masonry Construction" in prompt

    def test_prompt_contains_gewerk_name(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        prompt = agent._build_user_prompt(relevant_candidate, maurer_profil)
        assert "Maurer" in prompt

    def test_prompt_contains_kernkompetenzen(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        prompt = agent._build_user_prompt(relevant_candidate, maurer_profil)
        assert "Mauerwerksbau" in prompt

    def test_prompt_contains_frequency(self, maurer_profil, relevant_candidate):
        agent = TopicEvaluatorAgent()
        prompt = agent._build_user_prompt(relevant_candidate, maurer_profil)
        assert str(relevant_candidate.frequency) in prompt
