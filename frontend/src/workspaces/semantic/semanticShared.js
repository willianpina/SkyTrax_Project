/** Enrich topic rows with operational metadata for semantic bars. */
export function enrichTopicRows(rows = []) {
  const safe = Array.isArray(rows) ? rows : [];
  const max = Math.max(...safe.map((r) => r.weight ?? 0), 1);

  return safe.map((row) => {
    const weight = row.weight ?? 0;
    const pct = Math.round((weight / max) * 100);
    const samples = row.sample_size ?? Math.round(weight * 18.5);
    return { ...row, pct, samples, weight };
  });
}

export function semanticOverviewMetrics({ clusters = [], positive = [], negative = [] }) {
  const clusterList = Array.isArray(clusters) ? clusters : [];
  const reviewVolume = clusterList.reduce((sum, c) => sum + (c.review_count || 0), 0);
  const entityTerms = clusterList.reduce(
    (sum, c) => sum + (c.centroid_terms?.length || 0),
    0
  );

  return {
    clusterCount: clusterList.length,
    reviewVolume,
    positiveCount: (positive || []).length,
    negativeCount: (negative || []).length,
    entityTerms,
    pipelineActive: clusterList.length > 0 || (positive || []).length > 0,
  };
}
