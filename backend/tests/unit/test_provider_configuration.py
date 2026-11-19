from decimal import Decimal

from pydantic import ValidationError
import pytest

from app.providers.configuration import load_provider_config
from app.providers.ledger import cost_for
from app.providers.remote import clean_input


def test_preset_is_bounded_and_embedding_semantics_are_versioned():
    config = load_provider_config()
    assert config.chat.max_output_tokens == 1500 and config.chat.enable_thinking is False
    assert config.embedding.dimensions == 1024
    assert config.embedding.fingerprint("real") != config.embedding.fingerprint("contract")
    assert config.embedding.fingerprint() != config.embedding.model_copy(update={"dimensions": 3}).fingerprint()
    assert config.embedding.fingerprint() == config.embedding.model_copy(update={"input_price_per_million": 1.0}).fingerprint()


@pytest.mark.parametrize("url", ["http://public.example/v1", "https://user:secret@example.test/v1", "https://example.test/v1?key=secret", "file:///etc/password"])
def test_endpoint_rejects_embedded_credentials_and_insecure_remote_http(url):
    config = load_provider_config()
    with pytest.raises(ValidationError):
        type(config.chat).model_validate({**config.chat.model_dump(), "base_url": url})


def test_price_calculation_uses_explicit_currency_rates_and_unknown_is_not_zero():
    config = load_provider_config()
    assert cost_for(config.chat, 1000000, 1000000) == Decimal("3.60000000")
    assert cost_for(config.chat, None, None) is None


def test_provider_redaction_keeps_large_allowed_text_and_masks_sensitive_fields():
    value = clean_input({"customer_email": "private@example.test", "nested": {"api_key": "PRIVATE"}, "text": "连接" * 7000})
    assert value["customer_email"] == value["nested"]["api_key"] == "[REDACTED]"
    assert len(value["text"]) == 14000


def test_live_suite_missing_key_stops_before_database_or_network(monkeypatch, capsys):
    import json
    from types import SimpleNamespace
    from app.eval import live
    def forbidden(*args, **kwargs):
        pytest.fail("无 Key 时不应创建数据库或网络连接")
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(provider_api_key=None))
    monkeypatch.setattr(live.psycopg, "connect", forbidden)
    monkeypatch.setattr(live, "create_engine", forbidden)
    monkeypatch.setattr(live, "ProviderSession", forbidden)
    assert live.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "PROVIDER_KEY_MISSING" and result["real_acceptance"] is False
