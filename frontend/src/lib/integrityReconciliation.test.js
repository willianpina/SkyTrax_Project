/**
 * Defensive integrity reconciliation tests (node --test).
 * Run: npm test
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  extractLiveKpis,
  getNestedValue,
  reconcileIntegrityDisplay,
  reconcileIntegrityDisplaySafe,
  resetReconciliationMetrics,
  stageMetric,
} from "./integrityReconciliation.js";

describe("integrityReconciliation defensive", () => {
  it("getNestedValue does not throw when fusion is undefined", () => {
    assert.equal(getNestedValue({ fusion: undefined }, "fusion.signals_generated"), undefined);
    assert.equal(getNestedValue(undefined, "fusion.signals_generated"), undefined);
    assert.doesNotThrow(() => stageMetric({ fusion: undefined }, "fusion", "fusion.signals_generated"));
  });

  it("stageMetric returns 0 when metrics missing", () => {
    assert.equal(stageMetric(null, "fusion", "signals_generated"), 0);
    assert.equal(stageMetric({ fusion: null }, "fusion", "fusion.signals_generated"), 0);
    assert.equal(stageMetric({ fusion: {} }, "fusion", "fusion.signals_generated"), 0);
  });

  it("extractLiveKpis survives malformed stage_results", () => {
    const kpis = extractLiveKpis({ signals: 1123 }, { fusion: undefined });
    assert.equal(kpis.signals, 1123);
    assert.doesNotThrow(() => extractLiveKpis(null, undefined));
  });

  it("reconcileIntegrityDisplay survives null integrity", () => {
    resetReconciliationMetrics();
    const out = reconcileIntegrityDisplay(null, { metadata: 100 }, null);
    assert.ok(out.display);
    assert.equal(out.display.metadata, 100);
    assert.equal(out.table_counts.review_intelligence, 100);
  });

  it("reconcileIntegrityDisplay merges fusion nested metrics", () => {
    const out = reconcileIntegrityDisplay(
      { table_counts: {} },
      {},
      { fusion: { "fusion.signals_generated": 50 } },
    );
    assert.equal(out.display.signals, 50);
  });

  it("reconcileIntegrityDisplaySafe never returns missing display", () => {
    const out = reconcileIntegrityDisplaySafe(undefined, undefined, undefined);
    assert.ok(out.display);
    assert.equal(typeof out.display.signals, "number");
  });

  it("empty payload does not throw", () => {
    assert.doesNotThrow(() => reconcileIntegrityDisplay({}, {}, {}));
  });

  it("malformed fusion object with only signals_generated key", () => {
    const out = reconcileIntegrityDisplay({}, {}, { fusion: { signals_generated: 99 } });
    assert.equal(out.display.signals, 99);
  });

  it("reconciles graph_edges from knowledge_graph stage_results", () => {
    const out = reconcileIntegrityDisplay(
      { table_counts: { graph_edges: 0, graph_nodes: 100 } },
      { graph_edges: 0 },
      { knowledge_graph: { total_edges: 9492, total_nodes: 5224 }, fusion: { signals_generated: 155, fusion_status: "completed", enrichment_warning: true } },
    );
    assert.equal(out.display.graphEdges, 9492);
    assert.equal(out.display.signals, 155);
    assert.equal(out.partial, false);
    assert.equal(out.core_operational_healthy, true);
    assert.ok(out.display.graphEdges >= 9492);
    assert.ok(["stage_results", "runtime", "canonical_kpis", "postgres"].includes(
      out.kpi_lineage.graph_edges.graph_edges_source,
    ));
  });
});
