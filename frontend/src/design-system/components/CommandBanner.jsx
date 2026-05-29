import React from "react";

export function CommandBanner({ children, tone = "info" }) {
  return <div className={`sods-command-banner sods-command-banner--${tone}`}>{children}</div>;
}
