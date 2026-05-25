import React from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import CommandCenterLayout from "./layouts/CommandCenterLayout";

const ExecutiveWorkspace = React.lazy(() => import("./workspaces/executive/ExecutiveWorkspace"));
const BenchmarkingWorkspace = React.lazy(() => import("./workspaces/benchmarking/BenchmarkingWorkspace"));
const ReputationWorkspace = React.lazy(() => import("./workspaces/reputation/ReputationWorkspace"));
const SemanticWorkspace = React.lazy(() => import("./workspaces/semantic/SemanticWorkspace"));
const ForecastingWorkspace = React.lazy(() => import("./workspaces/forecasting/ForecastingWorkspace"));
const AnomaliesWorkspace = React.lazy(() => import("./workspaces/anomalies/AnomaliesWorkspace"));
const GeospatialWorkspace = React.lazy(() => import("./workspaces/geospatial/GeospatialWorkspace"));
const InvestigationsWorkspace = React.lazy(() => import("./workspaces/investigations/InvestigationsWorkspace"));

export const router = createBrowserRouter([
  {
    path: "/",
    element: <CommandCenterLayout />,
    children: [
      { index: true, element: <Navigate to="/executive" replace /> },
      { path: "executive", element: <ExecutiveWorkspace /> },
      { path: "benchmarking", element: <BenchmarkingWorkspace /> },
      { path: "reputation", element: <ReputationWorkspace /> },
      { path: "semantic", element: <SemanticWorkspace /> },
      { path: "forecasting", element: <ForecastingWorkspace /> },
      { path: "anomalies", element: <AnomaliesWorkspace /> },
      { path: "geospatial", element: <GeospatialWorkspace /> },
      { path: "investigations", element: <InvestigationsWorkspace /> },
      { path: "*", element: <Navigate to="/executive" replace /> }
    ]
  }
]);
