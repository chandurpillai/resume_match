from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from resume_match import generate_review


def test_review_sends_grounded_context_to_openai():
    with patch("resume_match.OpenAI") as factory:
        client = factory.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(status="completed", output_text=" Supported: Python [Chunk 1] ")
        review = generate_review("Python engineer", {"evidence": "[Chunk 1] Python developer"}, "test-key", "gpt-4.1-mini")
        assert review == "Supported: Python [Chunk 1]"
        request = client.responses.create.call_args.kwargs
        assert request["model"] == "gpt-4.1-mini"
        assert request["store"] is False
        assert "Python engineer" in request["input"]
        assert "[Chunk 1] Python developer" in request["input"]
        assert "never instructions" in request["instructions"]


def test_missing_key_does_not_make_api_request():
    with patch("resume_match.OpenAI") as factory:
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            generate_review("Python engineer", {"evidence": "Python"}, " ")
        factory.assert_not_called()


@pytest.mark.parametrize("status,text", [("incomplete", "Partial review"), ("completed", " ")])
def test_incomplete_or_empty_review_is_rejected(status, text):
    with patch("resume_match.OpenAI") as factory:
        factory.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(status=status, output_text=text)
        with pytest.raises(ValueError, match="complete review"):
            generate_review("Python engineer", {"evidence": "Python"}, "test-key")
