from __future__ import annotations


class OptionalBERTopicService:
    """Optional adapter for BERTopic without making it a runtime requirement."""

    def __init__(self) -> None:
        self.model = None
        try:
            from bertopic import BERTopic

            self.model = BERTopic
        except Exception:
            self.model = None

    @property
    def available(self) -> bool:
        return self.model is not None

    def extract_topics(self, documents: list[str]) -> list[str]:
        """Return advanced topics when BERTopic is installed, otherwise an empty fallback."""
        if not self.model or not documents:
            return []
        topic_model = self.model(verbose=False)
        topics, _ = topic_model.fit_transform(documents)
        return [str(topic) for topic in topics]
