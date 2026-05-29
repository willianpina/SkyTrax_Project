import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { resolveOperationalKpis, formatAviationThroughput } from "./kpiGovernance.js";

describe("kpiGovernance", () => {
  it("graph nodes and edges stay separate (5219 + 9480)", () => {
    const k = resolveOperationalKpis({
      kpis: { graph_nodes: 5219, graph_edges: 9480 },
      integrity: {},
      stageResults: {},
    });
    assert.equal(k.graphNodes, 5219);
    assert.equal(k.graphEdges, 9480);
    assert.equal(k.graphEntities, 14699);
  });

  it("aviation shows total vs this run", () => {
    const k = resolveOperationalKpis({
      kpis: {},
      integrity: {
        accumulated_kpis: { aviation_metadata_total: 1246, aviation_linked_total: 143 },
        delta_kpis: { aviation_processed_this_run: 2 },
      },
      stageResults: { aviation_master: { airlines_created: 1, airlines_updated: 1 } },
    });
    assert.equal(k.aviation.total, 1246);
    assert.equal(k.aviation.processedThisRun, 2);
    const t = (key, opts) => {
      if (key === "command:ops.throughput.aviationFull") {
        return `${opts.total} total · ${opts.linked} vinculadas · +${opts.run} nesta execução`;
      }
      return key;
    };
    const txt = formatAviationThroughput({}, k, t);
    assert.match(txt, /1.246 total/);
    assert.match(txt, /nesta execução/);
  });
});
