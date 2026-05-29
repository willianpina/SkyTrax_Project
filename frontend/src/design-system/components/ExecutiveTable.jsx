import React from "react";

export function ExecutiveTable({ columns = [], rows = [], loading = false, emptyLabel = "No operational records", className = "" }) {
  return (
    <div className={`sods-exec-table ${className}`.trim()} role="table" aria-busy={loading}>
      <div className="sods-exec-table__head" role="row">
        {columns.map((col) => (
          <span key={col.key} role="columnheader">{col.label}</span>
        ))}
      </div>
      {loading ? (
        Array.from({ length: 4 }).map((_, idx) => (
          <div key={idx} className="sods-exec-table__row" role="row">
            {columns.map((col) => (
              <span key={col.key} className="sods-skeleton" role="cell" />
            ))}
          </div>
        ))
      ) : rows.length ? (
        rows.map((row, idx) => (
          <div key={row.id || idx} className="sods-exec-table__row" role="row">
            {columns.map((col) => (
              <span key={col.key} role="cell">{col.render ? col.render(row) : row[col.key] ?? "-"}</span>
            ))}
          </div>
        ))
      ) : (
        <div className="sods-exec-table__empty">{emptyLabel}</div>
      )}
    </div>
  );
}
