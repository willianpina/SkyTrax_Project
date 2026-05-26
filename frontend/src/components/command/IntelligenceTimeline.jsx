import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { formatOperationalDateTime } from "../../utils/datetime";
import { PanelShell } from "../ui/PanelShell";

const TYPE_ICONS = {
  anomaly: "◆",
  insight: "●",
  forecast: "◇",
  crawl: "○",
  trend: "▲"
};

function IntelligenceTimelineInner({ items }) {
  const { t } = useTranslation("command");

  return (
    <PanelShell
      title={t("timeline.title")}
      subtitle={t("timeline.subtitle", { count: items.length })}
      accent="signal"
      expandable
      defaultExpanded={items.length > 0}
      className="timeline-panel"
    >
      {items.length === 0 ? (
        <p className="muted-copy">{t("timeline.empty")}</p>
      ) : (
        <ol className="intel-timeline">
          {items.map((item) => {
            const title = item.titleKey
              ? t(item.titleKey, { defaultValue: item.titleFallback })
              : item.titleFallback || item.title;

            const meta = item.metaKey
              ? t(item.metaKey, { ...item.metaParams, defaultValue: item.meta })
              : item.meta;

            return (
              <li className={`timeline-item type-${item.type} severity-${item.severity}`} key={item.id}>
                <span className="timeline-marker" aria-hidden>
                  {TYPE_ICONS[item.type] || "•"}
                </span>
                <div className="timeline-content">
                  <div className="timeline-head">
                    <strong>{title}</strong>
                    <time dateTime={item.timestamp}>{formatTime(item.timestamp)}</time>
                  </div>
                  {item.subtitle ? <span className="timeline-sub">{item.subtitle}</span> : null}
                  {meta ? <p className="timeline-meta">{meta}</p> : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </PanelShell>
  );
}

function formatTime(iso) {
  if (!iso) return "—";
  return formatOperationalDateTime(iso);
}

export const IntelligenceTimeline = memo(IntelligenceTimelineInner);
