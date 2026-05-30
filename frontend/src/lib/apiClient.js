import { logDomain } from "./domainAuditLog";

export const API_BASE = import.meta.env.VITE_API_BASE || "/api";

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
export async function fetchJson(path, fallback, { signal, domain } = {}) {
  const started = performance.now();
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal });
    const elapsed = Math.round(performance.now() - started);
    if (!response.ok) {
      console.warn(`[${domain || "API"}] api_request_failed`, { path, status: response.status, query_time_ms: elapsed });
      return fallback;
    }
    if (response.status === 204) {
      console.warn(`[${domain || "API"}] api_empty_response`, { path, status: 204, query_time_ms: elapsed, records_returned: 0 });
      return fallback;
    }
    const text = await response.text();
    if (!text || !text.trim()) {
      console.warn(`[${domain || "API"}] api_empty_body`, { path, query_time_ms: elapsed, records_returned: 0 });
      return fallback;
    }
    const data = JSON.parse(text);
    const count = Array.isArray(data)
      ? data.length
      : typeof data === "object" && data !== null
        ? Object.values(data).reduce((n, v) => n + (Array.isArray(v) ? v.length : 0), 0)
        : 0;
    if (domain) {
      logDomain(domain, {
        endpoint: path,
        recordsReturned: count,
        extra: { query_time_ms: elapsed, response_size: text.length },
      });
    }
    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      return fallback;
    }
    console.warn(`[${domain || "API"}] api_request_error`, path, error);
    return fallback;
  }
}
