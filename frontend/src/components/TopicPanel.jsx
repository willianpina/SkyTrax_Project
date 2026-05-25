import { memo } from "react";
import { useTranslation } from "react-i18next";
import { PanelShell } from "./ui/PanelShell";

function TopicPanelInner({ title, rows = [], tone }) {
  const { t } = useTranslation("dashboard");
  const safeRows = Array.isArray(rows) ? rows : [];
  const max = Math.max(...safeRows.map((row) => row.weight ?? 0), 1);

  return (
    <PanelShell title={title} subtitle={t("topics.weight")} accent={tone === "negative" ? "risk" : "positive"}>
      <div className="topic-list tactical">
        {safeRows.map((row) => (
          <div className="topic-row hover-intel" key={row.label}>
            <div>
              <strong>{row.label}</strong>
              <span>
                {row.sample_size ? t("topics.samples", { count: row.sample_size }) : t("topics.prioritySignal")}
              </span>
            </div>
            <div className="bar-track">
              <div className={tone} style={{ width: `${(row.weight / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  );
}

export const TopicPanel = memo(TopicPanelInner);
