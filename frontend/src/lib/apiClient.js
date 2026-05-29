export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export const FALLBACK_ANALYTICS = {
  average_rating: 7.8,
  review_count: 1240,
  recommendation_rate: 0.72,
  sentiment_distribution: { positive: 684, neutral: 221, negative: 335 },
  timeline: [
    { month: "2026-01-01", average_rating: 7.2, count: 140 },
    { month: "2026-02-01", average_rating: 7.6, count: 182 },
    { month: "2026-03-01", average_rating: 8.0, count: 211 },
    { month: "2026-04-01", average_rating: 7.4, count: 190 },
    { month: "2026-05-01", average_rating: 8.2, count: 256 }
  ],
  top_positive_topics: [
    { label: "cabin crew", weight: 42, sample_size: 775 },
    { label: "seat comfort", weight: 36, sample_size: 664 },
    { label: "smooth boarding", weight: 25, sample_size: 462 }
  ],
  top_negative_topics: [
    { label: "delayed baggage", weight: 39, sample_size: 721 },
    { label: "refund handling", weight: 31, sample_size: 573 },
    { label: "legroom", weight: 24, sample_size: 444 }
  ]
};

export const EMPTY_BENCHMARKING = {
  leaders: [],
  airlines: [],
  topic_heatmap: {},
  radar_analytics: [],
  operational_risk: {},
  complaint_density: {}
};

/**
 * JSON fetch with optional AbortSignal (polling governance).
 */
export async function fetchJson(path, fallback, { signal } = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal });
    if (!response.ok) {
      console.warn("api_request_failed", path, response.status);
      return fallback;
    }
    if (response.status === 204) {
      console.warn("api_empty_response", path, response.status);
      return fallback;
    }
    const text = await response.text();
    if (!text || !text.trim()) {
      return fallback;
    }
    return JSON.parse(text);
  } catch (error) {
    if (error?.name === "AbortError") {
      return fallback;
    }
    console.warn("api_request_error", path, error);
    return fallback;
  }
}
