from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import get_settings


@dataclass(frozen=True)
class NLPAnalysis:
    cleaned_text: str
    sentiment_label: str
    sentiment_score: float
    topics: list[str]
    entities: list[dict[str, str]]
    embedding: list[float] | None
    model_versions: dict[str, str]


class ReviewNLPPipeline:
    """Lightweight NLP pipeline with optional heavy model loading.

    The default path is CPU-only and fast to initialize: lexicon sentiment,
    spaCy entities with blank fallback and TF-IDF topics. Sentence-transformers
    embeddings are loaded only when NLP_ENABLE_EMBEDDINGS=true.
    """

    positive_terms = {
        "excellent",
        "great",
        "comfortable",
        "friendly",
        "clean",
        "efficient",
        "smooth",
        "helpful",
    }
    negative_terms = {
        "delayed",
        "rude",
        "poor",
        "dirty",
        "cancelled",
        "lost",
        "bad",
        "uncomfortable",
        "refund",
    }

    def __init__(
        self, embedding_model_name: str | None = None, enable_embeddings: bool | None = None
    ) -> None:
        settings = get_settings()
        self.enable_embeddings = (
            settings.nlp_enable_embeddings if enable_embeddings is None else enable_embeddings
        )
        self.embedding_model_name = embedding_model_name or settings.nlp_embedding_model

        try:
            self.nlp = spacy.load("en_core_web_sm")
            spacy_model = "en_core_web_sm"
        except OSError:
            self.nlp = spacy.blank("en")
            spacy_model = "spacy_blank_en"

        self.embedding_model = None
        if self.enable_embeddings:
            try:
                from sentence_transformers import SentenceTransformer

                self.embedding_model = SentenceTransformer(self.embedding_model_name, device="cpu")
            except Exception:
                self.embedding_model = None

        self.model_versions = {
            "spacy": spacy_model,
            "sentiment": "lexicon-v1",
            "topics": "tfidf-fallback-v1",
            "embeddings": self.embedding_model_name if self.embedding_model else "disabled-or-unavailable",
            "advanced_topics": "optional",
            "transformers": "transitive-optional",
        }

    def analyze(self, text: str) -> NLPAnalysis:
        cleaned = self.clean_text(text)
        tokens = self.tokenize(cleaned)
        sentiment_score = self.sentiment_score(tokens)
        label = "positive" if sentiment_score > 0.15 else "negative" if sentiment_score < -0.15 else "neutral"
        doc = self.nlp(cleaned)
        return NLPAnalysis(
            cleaned_text=cleaned,
            sentiment_label=label,
            sentiment_score=sentiment_score,
            topics=self.topic_keywords([cleaned]),
            entities=[{"text": ent.text, "label": ent.label_} for ent in doc.ents],
            embedding=self.embed(cleaned),
            model_versions=self.model_versions,
        )

    @staticmethod
    def clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^A-Za-z0-9 .,;:!?'-]", "", text)
        return text.strip()

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[A-Za-z']+", text)]

    def sentiment_score(self, tokens: list[str]) -> float:
        counts = Counter(tokens)
        positive = sum(counts[token] for token in self.positive_terms)
        negative = sum(counts[token] for token in self.negative_terms)
        total = max(positive + negative, 1)
        return round((positive - negative) / total, 4)

    def embed(self, text: str) -> list[float] | None:
        if not self.embedding_model or not text:
            return None
        vector = self.embedding_model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]

    @staticmethod
    def topic_keywords(documents: list[str], top_n: int = 5) -> list[str]:
        if not documents or not any(documents):
            return []
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=80)
        try:
            matrix = vectorizer.fit_transform(documents)
        except ValueError:
            return []
        scores = matrix.sum(axis=0).A1
        features = vectorizer.get_feature_names_out()
        ranked = sorted(zip(features, scores), key=lambda item: item[1], reverse=True)
        return [feature for feature, _ in ranked[:top_n]]
