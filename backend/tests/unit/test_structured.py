from app.eval.structured import Corpus, Scope, chunk_search, claim_search


def test_claims_withdrawn_draft_or_wrong_version_cannot_bypass_scope_filter():
    base = {"entity": "demo", "firmware": "1.0", "document_version": 1, "effective_from": "2026-01-01",
            "text": "支持的端口数量"}
    corpus = Corpus(chunks=[
        {**base, "ref": "first"},
        {**base, "ref": "opposite"},
        {**base, "ref": "pending"},
        {**base, "ref": "v2", "firmware": "2.0"},
        {**base, "ref": "case", "source_type": "experience"},
    ], claims=[
        {"chunk_ref": "first", "field": "ports", "value": "1"},
        {"chunk_ref": "opposite", "field": "ports", "value": "2"},
        {"chunk_ref": "pending", "field": "ports", "value": "10", "status": "draft"},
        {"chunk_ref": "v2", "field": "ports", "value": "5"},
        {"chunk_ref": "case", "field": "ports", "value": "99"},
    ], aliases={"ports": ["端口数量", "几个口"]})
    scope = Scope(entity="demo", firmware="1.0", as_of="2026-11-21")
    assert set(chunk_search(corpus, scope, "支持的端口数量？")) == {"first", "opposite"}
    assert claim_search(corpus, scope, "几个口？") == {"status": "conflict", "refs": ["first", "opposite"]}
    assert claim_search(corpus, scope.model_copy(update={"firmware": None}), "几个口？")["refs"] == []
