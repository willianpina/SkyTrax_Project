import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

const EMPTY = { metrics: {}, airlines: [], generated_at: null };

export function useForecasting() {
  const [forecasts, setForecasts] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchJson("/forecasting", EMPTY);
    setForecasts(result?.metrics ? result : EMPTY);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return { forecasts, loading, reload: load };
}
