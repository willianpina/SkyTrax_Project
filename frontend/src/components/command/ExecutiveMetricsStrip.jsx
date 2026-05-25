import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { TrendArrow } from "../ui/PanelShell";

function ExecutiveMetricsStripInner({ metrics, loading }) {
  const { t } = useTranslation("command");

  if (loading) {
    return (
      <section className="metrics-strip">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div className="strip-metric skeleton" key={i} />
        ))}
      </section>
    );
  }

  return (
    <section className="metrics-strip" aria-label={t("metrics.stripLabel")}>
      {metrics.map((m) => (
        <div className={`strip-metric severity-${m.severity}`} key={m.id}>
          <span className="strip-label">{t(m.labelKey)}</span>
          <div className="strip-value-row">
            <span className="strip-value">
              {m.value}
              {m.unit ? <small>{m.unit}</small> : null}
            </span>
            <TrendArrow direction={m.trend} />
          </div>
          <span className="strip-indicator" aria-hidden />
        </div>
      ))}
    </section>
  );
}

export const ExecutiveMetricsStrip = memo(ExecutiveMetricsStripInner);
