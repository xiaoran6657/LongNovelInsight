from services.parser_service import (
    _detect_chapters,
    _estimate_tokens,
    _split_into_chunks,
)

# ── Chapter detection ──


def test_detect_chinese_chapter_number():
    text = "第1章 开始\n一些内容\n第2章 继续\n更多内容"
    result = _detect_chapters(text)
    assert len(result) == 2
    assert result[0]["title"] == "第1章 开始"
    assert result[1]["title"] == "第2章 继续"


def test_detect_chinese_chapter_hanzi():
    text = "第一章 开篇\n正文\n第二章 发展\n正文"
    result = _detect_chapters(text)
    assert len(result) == 2
    assert result[0]["title"] == "第一章 开篇"


def test_detect_chinese_hui():
    text = "第一回 开始\n内容\n第二回 继续\n内容"
    result = _detect_chapters(text)
    assert len(result) == 2
    assert result[0]["title"] == "第一回 开始"


def test_detect_english_chapter():
    text = "Chapter 1 Start\ncontent\nChapter 2 Continue\ncontent"
    result = _detect_chapters(text)
    assert len(result) == 2
    assert result[0]["title"] == "Chapter 1 Start"


def test_detect_english_chapter_upper():
    text = "CHAPTER 1 START\ncontent\nCHAPTER 2 CONTINUE\ncontent"
    result = _detect_chapters(text)
    assert len(result) == 2


def test_fallback_full_text():
    text = "这是一段没有章节标题的文本。\n没有任何模式匹配。"
    result = _detect_chapters(text)
    assert len(result) == 1
    assert result[0]["title"] == "Full Text"
    assert result[0]["start_char"] == 0


def test_detect_chinese_jie():
    text = "第一节 概述\n内容\n第二节 详情\n内容"
    result = _detect_chapters(text)
    assert len(result) == 2
    assert result[0]["title"] == "第一节 概述"


def test_ignore_chapter_pattern_in_body():
    text = "正文开始\n某人说第1章很重要\n第二章 正式章节\n内容"
    result = _detect_chapters(text)
    # "第1章很重要" is not at line start, so it should NOT match
    # But "第1章很重要" could match if the line starts with it... actually it's mid-line
    # Only "第二章 正式章节" starts at beginning of line
    assert len(result) == 1
    assert result[0]["title"] == "第二章 正式章节"


def test_long_title_not_detected():
    # Title > 80 chars should not be treated as chapter heading
    text = "第1章 " + ("X" * 80) + "\n内容"
    result = _detect_chapters(text)
    assert len(result) == 1
    assert result[0]["title"] == "Full Text"


# ── Chunk splitting ──


def test_short_text_one_chunk():
    text = "A" * 2000
    chunks = _split_into_chunks(text, 0, len(text))
    assert len(chunks) == 1
    assert chunks[0] == (0, 2000)


def test_long_text_many_chunks():
    text = "A" * 12000
    chunks = _split_into_chunks(text, 0, len(text))
    assert len(chunks) >= 3
    assert chunks[0][0] == 0
    assert chunks[-1][1] == 12000


def test_overlap_between_chunks():
    text = "A" * 10000
    chunks = _split_into_chunks(text, 0, len(text))
    assert len(chunks) >= 2
    assert chunks[1][0] < chunks[0][1]


def test_within_chapter_boundary():
    text = "A" * 3000 + "第1章" + "B" * 3000
    chunks = _split_into_chunks(text, 3000, len(text))
    assert len(chunks) == 1
    assert chunks[0][0] >= 3000


# ── Token estimation ──


def test_estimate_tokens_positive():
    assert _estimate_tokens(1) >= 1
    assert _estimate_tokens(100) >= 1
    assert _estimate_tokens(1500) >= 1


def test_estimate_tokens_chinese_ratio():
    assert _estimate_tokens(1500) == 1000


def test_estimate_tokens_rounds_up():
    assert _estimate_tokens(2) == 2


# ── Offset scanning ──


def test_chapter_start_char_correct():
    text = "第一章 开篇\n正文内容\n第二章 发展\n更多"
    result = _detect_chapters(text)
    assert len(result) == 2
    # "第一章 开篇\n" is at offset 0
    assert result[0]["start_char"] == 0
    # "第二章 发展\n" starts after "第一章 开篇\n正文内容\n"
    # Line 1: "第一章 开篇\n" = len("第一章 开篇") + 1 = 8
    # Line 2: "正文内容\n" = len("正文内容") + 1 = 5
    # Total = 13
    expected_offset = len("第一章 开篇\n" + "正文内容\n")
    assert result[1]["start_char"] == expected_offset
