from nlp.pipeline import ReviewNLPPipeline


def test_lightweight_nlp_pipeline_runs_without_embeddings() -> None:
    pipeline = ReviewNLPPipeline(enable_embeddings=False)
    result = pipeline.analyze("Excellent cabin crew and smooth boarding, but delayed baggage handling.")

    assert result.cleaned_text
    assert result.sentiment_label in {"positive", "neutral", "negative"}
    assert result.embedding is None
    assert "topics" in result.model_versions


def test_topic_keywords_returns_ranked_terms() -> None:
    topics = ReviewNLPPipeline.topic_keywords(["delayed baggage delayed refund cabin crew"], top_n=3)

    assert topics
    assert any("delayed" in topic for topic in topics)
