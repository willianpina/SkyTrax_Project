import React from "react";

export function OperationalStatusBar({ items = [], className = "", renderItem }) {
  if (!items.length) return null;
  return (
    <div className={`sods-operational-status-bar ${className}`.trim()}>
      {items.map((item, idx) => (
        <React.Fragment key={item.key || idx}>
          {renderItem ? renderItem(item) : item.content}
        </React.Fragment>
      ))}
    </div>
  );
}
