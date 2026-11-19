import pytest
from pydantic import ValidationError

from app.knowledge.schemas import DocumentMetadata
from app.knowledge.text import IngestionFailure, bm25_scores, split_document, tokenize


def test_chinese_terms_models_and_error_codes_share_the_same_tokenizer():
    terms = tokenize("行驶中连接失败 PILOT-01 E_WIFI_401 v1.2.3 ＡＢＣ")
    assert {"连接", "失败", "pilot-01", "e_wifi_401", "v1.2.3", "abc"} <= set(terms)
    assert "pilot" not in terms and "01" not in terms


def test_bm25_numeric_ranking_length_and_no_match():
    docs = {"short": {"tf": {"x": 2}, "length": 2}, "long": {"tf": {"x": 1, "y": 4}, "length": 5}}
    scores = dict(bm25_scores(docs, "x"))
    # 两篇都含 x，IDF=ln(1.2)，平均长度3.5；短文重复词的饱和权重更高。
    assert scores["short"] == pytest.approx(0.285050961891056, rel=1e-10)
    assert scores["short"] > scores["long"]
    assert bm25_scores(docs, "x x x") == bm25_scores(docs, "x")
    assert bm25_scores(docs, "unseen") == bm25_scores({}, "x") == []


def test_markdown_headings_fences_steps_and_source_lines():
    source = "# 指南\n前言\n## 连接\n1. 检查型号。\n2. 查看 E_WIFI_401。\n```text\n# 代码中的标题\n```\n## 恢复\n请重新确认。"
    chunks = split_document(source.encode(), "guide.md")
    assert [row.heading_path for row in chunks] == [["指南"], ["指南", "连接"], ["指南", "恢复"]]
    assert chunks[1].start_line == 3 and chunks[1].end_line == 8
    assert "1. 检查型号。\n2. 查看 E_WIFI_401。" in chunks[1].text
    assert "# 代码中的标题" in chunks[1].text
    assert split_document(b"# literal\nplain text", "guide.txt")[0].heading_path == []
    skipped = split_document("### 先三级\n正文\n## 再二级\n正文".encode(), "guide.md")
    assert skipped[1].heading_path == ["再二级"]


def test_long_sections_keep_content_overlap_and_parent_positions():
    lines = [f"步骤{number:04d}：核对连接事件和对应设备，保留上下文以便人工检查。" for number in range(120)]
    chunks = split_document(("# 长指南\n" + "\n".join(lines)).encode(), "long.md")
    assert len(chunks) > 3 and all(len(row.text) <= 1000 for row in chunks)
    assert all(any(line in row.text for row in chunks) for line in lines)
    assert chunks[0].text[-100:] == chunks[1].text[:100]
    assert all(row.heading_path == ["长指南"] and row.parent_start_line == 1 and row.parent_end_line == 121 for row in chunks)


def test_utf8_bom_crlf_and_redaction_do_not_silently_truncate_valid_text():
    source = "# 指南\r\nAuthorization: Bearer TEST_ONLY_SECRET\r\npassword=TEST_ONLY_SECRET\r\n连接检查。"
    chunks = split_document(b"\xef\xbb\xbf" + source.encode(), "guide.md")
    assert chunks[0].end_line == 4 and "TEST_ONLY_SECRET" not in chunks[0].text
    assert "连接检查。" in chunks[0].text and "[REDACTED]" in chunks[0].text


@pytest.mark.parametrize("raw,code", [
    (b"\xff\xfe", "INVALID_UTF8"), (b"\x00abc", "INVALID_TEXT"), (b"  \n\t", "EMPTY_DOCUMENT"),
    (b"", "EMPTY_FILE"), (b"x" * 4097, "LINE_TOO_LONG"), (b"x" * (1024 * 1024 + 1), "FILE_TOO_LARGE"),
    (b"!!!", "EMPTY_DOCUMENT"),
])
def test_parser_failures_have_safe_distinct_error_codes(raw, code):
    with pytest.raises(IngestionFailure) as exc:
        split_document(raw, "guide.txt")
    assert exc.value.code == code


def test_metadata_requires_explicit_scope_and_rejects_mixed_wildcards():
    metadata = {"doc_key": "guide", "version": 1, "title": "指南", "product_scope": ["PILOT-01"],
                "firmware_versions": ["1.0"], "regions": ["*"], "channels": ["*"]}
    assert DocumentMetadata(**metadata).product_scope == ["PILOT-01"]
    for changed in ({"regions": []}, {"product_scope": ["*", "PILOT-01"]}, {"status": "active"},
                    {"effective_from": "2026-11-20T00:00:00Z", "effective_to": "2026-11-19T00:00:00Z"}):
        with pytest.raises(ValidationError):
            DocumentMetadata(**{**metadata, **changed})
