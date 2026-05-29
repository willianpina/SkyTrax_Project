import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, Radio } from "lucide-react";
import { buildRatingOption } from "../../lib/chartConfigs";
import { forecastConfidence } from "../../lib/executiveMetrics";
import { ForecastPanel } from "../../components/ForecastPanel";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { ConfidenceBadge } from "../../components/ui/PanelShell";

function OperationalForecastChartsInner({ forecasts, ratingTimeline }) {
  const { t, i18n } = useTranslation(["charts", "command", "common"]);

  const ratingOption = useMemo(
    () => buildRatingOption(ratingTimeline, i18n.language),
    [ratingTimeline, i18n.language]
  );

  const ratingKpis = useMemo(() => {
    if (!ratingTimeline.length) return [];
    const values = ratingTimeline.map((row) => row.average_rating ?? row.score / 10);
    const latest = values[values.length - 1];
    const prev = values.length > 1 ? values[values.length - 2] : null;
    const delta = prev != null ? latest - prev : null;
    const deltaFmt = delta != null ? `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}` : "—";
    return [
      {
        label: t("charts:ratingEvolution.kpiLatest", { defaultValue: "Latest rating" }),
        value: latest != null ? latest.toFixed(2) : "—",
        accent: "positive",
      },
      {
        label: t("charts:ratingEvolution.kpiDelta", { defaultValue: "Period Δ" }),
        value: deltaFmt,
        accent: delta != null && delta < 0 ? "risk" : delta > 0 ? "positive" : "muted",
      },
      {
        label: t("charts:ratingEvolution.kpiWindow", { defaultValue: "Window" }),
        value: t("charts:ratingEvolution.periods", {
          count: ratingTimeline.length,
          defaultValue: `${ratingTimeline.length} mo`,
        }),
        accent: "signal",
      },
    ];
  }, [ratingTimeline, t]);

  const primary = (forecasts?.metrics?.reputation_score || []).find((r) => r.horizon === "weekly");
  const conf = forecastConfidence(primary);

  const status = (
    <>
      <span className="op-status-pill">
        <Radio size={12} aria-hidden />
        {t("charts:operationalForecast.statusPipeline", { defaultValue: "Pipeline active" })}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Activity size={12} aria-hidden />
        {t("charts:operationalForecast.horizon", { defaultValue: "Weekly horizon" })}
      </span>
      <ConfidenceBadge
        score={conf.score}
        insufficient={conf.insufficient}
        label={
          conf.insufficient
            ? t("charts:reputationForecast.warmingUp", { defaultValue: "Warming up" })
            : t("command:forecast.confidence", { score: conf.score })
        }
      />
    </>
  );

  return (
    <OperationalModuleCard
      className="forecast-charts-module"
      title={t("charts:operationalForecast.title", { defaultValue: "Operational Forecast" })}
      subtitle={t("charts:operationalForecast.subtitle", {
        defaultValue: "Portfolio reputation projection and rating trajectory",
      })}
      status={status}
      bodyClassName="forecast-charts-module__body"
    >
      <div className="forecast-charts-module__grid">
        <div className="op-module-pane op-module-pane--forecast">
          <ForecastPanel forecasts={forecasts} embedded chartHeight={240} />
        </div>
        <div className="op-module-pane op-module-pane--rating">
          <ChartPanel
            embedded
            variant="executive"
            title={t("charts:ratingEvolution.title")}
            subtitle={t("charts:ratingEvolution.subtitle")}
            option={ratingOption}
            accent="positive"
            height={240}
            kpis={ratingKpis}
            legend={[
              {
                label: t("charts:ratingEvolution.series", { defaultValue: "Avg. rating" }),
                tone: "positive",
              },
            ]}
            emptyMessage={t("charts:ratingEvolution.empty", {
              defaultValue: "Rating history will populate after the first operational snapshot.",
            })}
          />
        </div>
      </div>
    </OperationalModuleCard>
  );
}

export const OperationalForecastCharts = memo(OperationalForecastChartsInner);
