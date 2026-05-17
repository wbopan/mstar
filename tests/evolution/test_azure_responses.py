"""Tests for the codex Responses-API adapter (azure_responses)."""

from __future__ import annotations

from types import SimpleNamespace

from mstar.evolution.azure_responses import (
    RESPONSES_PREFIX,
    _adapt_response,
    _build_create_kwargs,
    _deployment_name,
    is_responses_model,
)


class TestIsResponsesModel:
    def test_true_for_responses_prefix(self):
        assert is_responses_model("azure/responses/gpt-5.3-codex") is True

    def test_false_for_plain_azure_model(self):
        assert is_responses_model("azure/gpt-5.1") is False

    def test_false_for_non_azure_model(self):
        assert is_responses_model("openrouter/baai/bge-m3") is False

    def test_false_for_none(self):
        assert is_responses_model(None) is False

    def test_false_for_non_string(self):
        assert is_responses_model(123) is False


class TestDeploymentName:
    def test_strips_prefix(self):
        assert _deployment_name("azure/responses/gpt-5.3-codex") == "gpt-5.3-codex"

    def test_prefix_constant_matches(self):
        assert RESPONSES_PREFIX == "azure/responses/"


class TestBuildCreateKwargs:
    def test_messages_become_input(self):
        msgs = [{"role": "user", "content": "hi"}]
        out = _build_create_kwargs({"model": "azure/responses/gpt-5.3-codex", "messages": msgs})
        assert out["model"] == "gpt-5.3-codex"
        assert out["input"] == msgs

    def test_missing_messages_yields_empty_input(self):
        out = _build_create_kwargs({"model": "azure/responses/gpt-5.3-codex"})
        assert out["input"] == []

    def test_reasoning_effort_mapped(self):
        out = _build_create_kwargs(
            {"model": "azure/responses/gpt-5.3-codex", "messages": [], "reasoning_effort": "high"}
        )
        assert out["reasoning"] == {"effort": "high"}

    def test_no_reasoning_key_when_effort_absent(self):
        out = _build_create_kwargs({"model": "azure/responses/gpt-5.3-codex", "messages": []})
        assert "reasoning" not in out

    def test_max_completion_tokens_mapped(self):
        out = _build_create_kwargs(
            {"model": "azure/responses/c", "messages": [], "max_completion_tokens": 2048}
        )
        assert out["max_output_tokens"] == 2048

    def test_max_tokens_mapped(self):
        out = _build_create_kwargs({"model": "azure/responses/c", "messages": [], "max_tokens": 256})
        assert out["max_output_tokens"] == 256

    def test_temperature_passed_through(self):
        out = _build_create_kwargs(
            {"model": "azure/responses/c", "messages": [], "temperature": 0.0}
        )
        assert out["temperature"] == 0.0

    def test_litellm_only_kwargs_dropped(self):
        """caching / api_base / api_version / token provider must not leak through."""
        out = _build_create_kwargs(
            {
                "model": "azure/responses/c",
                "messages": [],
                "caching": True,
                "api_base": "https://x.azure.com",
                "api_version": "2025-03-01-preview",
                "azure_ad_token_provider": lambda: "tok",
            }
        )
        for leaked in ("caching", "api_base", "api_version", "azure_ad_token_provider"):
            assert leaked not in out


class TestAdaptResponse:
    def test_extracts_output_text(self):
        resp = SimpleNamespace(output_text="hello world")
        mr = _adapt_response(resp, "azure/responses/gpt-5.3-codex")
        assert mr.choices[0].message.content == "hello world"
        assert mr.choices[0].message.role == "assistant"
        assert mr.model == "azure/responses/gpt-5.3-codex"

    def test_missing_output_text_yields_empty_string(self):
        resp = SimpleNamespace()
        mr = _adapt_response(resp, "azure/responses/c")
        assert mr.choices[0].message.content == ""

    def test_none_output_text_yields_empty_string(self):
        resp = SimpleNamespace(output_text=None)
        mr = _adapt_response(resp, "azure/responses/c")
        assert mr.choices[0].message.content == ""
