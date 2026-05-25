import React, { memo, Suspense, lazy } from "react";

const ReactECharts = lazy(() =>
  import("echarts-for-react").then((module) => ({
    default: module.default ?? module
  }))
);

function ChartSkeleton({ height }) {
  return <div className="chart-skeleton tactical" style={{ height: height || 240 }} aria-hidden />;
}

function LazyEChartInner({ option, height = 260, className = "" }) {
  if (!option) {
    return <ChartSkeleton height={height} />;
  }
  return (
    <Suspense fallback={<ChartSkeleton height={height} />}>
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        className={className}
        notMerge
        lazyUpdate
        opts={{ renderer: "canvas" }}
      />
    </Suspense>
  );
}

export const LazyEChart = memo(LazyEChartInner);
