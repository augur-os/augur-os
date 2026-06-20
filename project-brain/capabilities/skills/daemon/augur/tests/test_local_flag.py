"""Tests for --local flag in adaptive loop executor."""
import pytest
from src.lib.ops_protocol import OpsContext


class TestOpsContextClient:
    def test_default_client_is_none(self):
        ctx = OpsContext()
        assert ctx.client is None

    def test_client_can_be_set(self):
        ctx = OpsContext(client="ollama")
        assert ctx.client == "ollama"
