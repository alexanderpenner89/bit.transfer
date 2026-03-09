"""Tests for ArticleGeneratorAgent feedback loop."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.article_generator import ArticleDeps, ArticleGeneratorAgent, ArticleGewerksContext, ArticleWorkInput
from schemas.publication_pipeline import WorkSummary


def _make_deps() -> ArticleDeps:
    return ArticleDeps(
        work_id="W123",
        work=ArticleWorkInput(
            title="Test Publikation",
            abstract="Ein Test.",
            doi="10.1234/test",
            publication_year=2024,
            citation_count=5,
        ),
        perspectives=[],
        gewerk_context=ArticleGewerksContext(
            gewerk_name="Maurer",
            kernkompetenzen=["Mauern", "Verputzen"],
        ),
        research_questions=["Was ist TRL?"],
    )


def test_generate_no_retry_when_validation_passes():
    """Agent.run is called only once when validation passes on first attempt."""
    agent = ArticleGeneratorAgent(model="test")

    fake_output = MagicMock()
    fake_output.title = "Titel"
    fake_output.html = "<article>ok</article>"
    fake_output.intro = "Intro."
    fake_output.key_learnings = ["Lernen"]

    fake_result = MagicMock()
    fake_result.output = fake_output
    fake_result.usage.return_value = MagicMock(input_tokens=10, output_tokens=20)
    fake_result.all_messages.return_value = []

    fake_val_output = MagicMock()
    fake_val_output.passed = True
    fake_val_output.issues = []

    with patch.object(agent.agent, "run", new=AsyncMock(return_value=fake_result)) as mock_run, \
         patch.object(agent, "_validate", new=AsyncMock(return_value=fake_val_output)):
        with patch("agents.article_generator.get_langfuse") as mock_lf:
            mock_lf.return_value.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_lf.return_value.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
            result = asyncio.run(agent.generate(_make_deps()))

    assert mock_run.call_count == 1
    assert result.work_id == "W123"


def test_generate_retries_with_message_history_on_failure():
    """On validation failure, agent.run is called again with message_history set."""
    agent = ArticleGeneratorAgent(model="test")

    fake_output = MagicMock()
    fake_output.title = "Titel"
    fake_output.html = "<article>fixed</article>"
    fake_output.intro = "Intro."
    fake_output.key_learnings = ["Lernen"]

    fake_result = MagicMock()
    fake_result.output = fake_output
    fake_result.usage.return_value = MagicMock(input_tokens=10, output_tokens=20)
    history_sentinel = [object()]  # unique object to verify it's passed through
    fake_result.all_messages.return_value = history_sentinel

    # Validation: fail first, pass second
    fail_output = MagicMock()
    fail_output.passed = False
    fail_output.issues = [MagicMock(severity="major", description="Kein TRL-Badge")]

    pass_output = MagicMock()
    pass_output.passed = True
    pass_output.issues = []

    with patch.object(agent.agent, "run", new=AsyncMock(return_value=fake_result)) as mock_run, \
         patch.object(agent, "_validate", new=AsyncMock(side_effect=[fail_output, pass_output])):
        with patch("agents.article_generator.get_langfuse") as mock_lf:
            mock_lf.return_value.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_lf.return_value.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
            result = asyncio.run(agent.generate(_make_deps()))

    assert mock_run.call_count == 2
    # Second call must pass message_history
    second_call_kwargs = mock_run.call_args_list[1].kwargs
    assert second_call_kwargs["message_history"] is history_sentinel


def test_generate_stops_after_max_retries():
    """Loop does not exceed 2 retry attempts even if validation keeps failing."""
    agent = ArticleGeneratorAgent(model="test")

    fake_output = MagicMock()
    fake_output.title = "Titel"
    fake_output.html = "<article>still bad</article>"
    fake_output.intro = "Intro."
    fake_output.key_learnings = ["Lernen"]

    fake_result = MagicMock()
    fake_result.output = fake_output
    fake_result.usage.return_value = MagicMock(input_tokens=10, output_tokens=20)
    fake_result.all_messages.return_value = []

    always_fail = MagicMock()
    always_fail.passed = False
    always_fail.issues = [MagicMock(severity="critical", description="Fehler")]

    with patch.object(agent.agent, "run", new=AsyncMock(return_value=fake_result)) as mock_run, \
         patch.object(agent, "_validate", new=AsyncMock(return_value=always_fail)):
        with patch("agents.article_generator.get_langfuse") as mock_lf:
            mock_lf.return_value.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_lf.return_value.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
            result = asyncio.run(agent.generate(_make_deps()))

    # 1 initial + 2 retries = 3 total calls
    assert mock_run.call_count == 3


def test_validate_does_not_return_refined_html():
    """_validate returns only passed + issues, never refined_html."""
    agent = ArticleGeneratorAgent(model="test")

    fake_output = MagicMock()
    fake_output.html = "<article>test</article>"

    fake_val_result = MagicMock()
    val_out = MagicMock(spec=["passed", "issues"])  # no refined_html in spec
    val_out.passed = False
    val_out.issues = [MagicMock(severity="major", description="Problem")]
    fake_val_result.output = val_out

    with patch("agents.article_generator.Agent") as MockAgent:
        mock_validator = MagicMock()
        mock_validator.system_prompt = MagicMock(return_value=lambda f: f)
        mock_validator.run = AsyncMock(return_value=fake_val_result)
        MockAgent.return_value = mock_validator

        with patch("agents.article_generator.get_langfuse") as mock_lf:
            mock_lf.return_value.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_lf.return_value.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

            deps = _make_deps()
            result = asyncio.run(agent._validate(fake_output, deps))

    assert not hasattr(result, "refined_html") or result.refined_html is None
