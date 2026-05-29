/** Client-side fallback when API is unreachable — mirrors backend reference network */

export const OPERATIONAL_SEED = {
  airports: [
    { id: "seed-fra", iata: "FRA", name: "Frankfurt", city: "Frankfurt", country: "DE", latitude: 50.0379, longitude: 8.5622, hub_score: 0.92, reputation_score: 0.78 },
    { id: "seed-jfk", iata: "JFK", name: "JFK", city: "New York", country: "US", latitude: 40.6413, longitude: -73.7781, hub_score: 0.9, reputation_score: 0.72 },
    { id: "seed-dxb", iata: "DXB", name: "Dubai", city: "Dubai", country: "AE", latitude: 25.2532, longitude: 55.3657, hub_score: 0.94, reputation_score: 0.8 },
    { id: "seed-lhr", iata: "LHR", name: "Heathrow", city: "London", country: "GB", latitude: 51.47, longitude: -0.4543, hub_score: 0.93, reputation_score: 0.76 },
    { id: "seed-gru", iata: "GRU", name: "Guarulhos", city: "São Paulo", country: "BR", latitude: -23.4356, longitude: -46.4731, hub_score: 0.88, reputation_score: 0.68 },
    { id: "seed-mia", iata: "MIA", name: "Miami", city: "Miami", country: "US", latitude: 25.7959, longitude: -80.287, hub_score: 0.86, reputation_score: 0.7 },
    { id: "seed-sin", iata: "SIN", name: "Changi", city: "Singapore", country: "SG", latitude: 1.3644, longitude: 103.9915, hub_score: 0.95, reputation_score: 0.88 },
    { id: "seed-hkg", iata: "HKG", name: "Hong Kong", city: "Hong Kong", country: "HK", latitude: 22.308, longitude: 113.9185, hub_score: 0.91, reputation_score: 0.74 },
  ],
  routes: [
    { id: "seed-r1", source_icao: "FRA", destination_icao: "JFK", source_lat: 50.0379, source_lng: 8.5622, destination_lat: 40.6413, destination_lng: -73.7781, frequency: 420, risk_score: 0.18 },
    { id: "seed-r2", source_icao: "DXB", destination_icao: "LHR", source_lat: 25.2532, source_lng: 55.3657, destination_lat: 51.47, destination_lng: -0.4543, frequency: 510, risk_score: 0.22 },
    { id: "seed-r3", source_icao: "GRU", destination_icao: "MIA", source_lat: -23.4356, source_lng: -46.4731, destination_lat: 25.7959, destination_lng: -80.287, frequency: 280, risk_score: 0.35 },
    { id: "seed-r4", source_icao: "SIN", destination_icao: "LHR", source_lat: 1.3644, source_lng: 103.9915, destination_lat: 51.47, destination_lng: -0.4543, frequency: 390, risk_score: 0.15 },
    { id: "seed-r5", source_icao: "HKG", destination_icao: "FRA", source_lat: 22.308, source_lng: 113.9185, destination_lat: 50.0379, destination_lng: 8.5622, frequency: 310, risk_score: 0.28 },
  ],
};

export function mergeClientSeed(data) {
  const airports = Array.isArray(data?.airports) ? [...data.airports] : [];
  const routes = Array.isArray(data?.routes) ? [...data.routes] : [];
  let events = Array.isArray(data?.events) ? [...data.events] : [];
  let seeded = Boolean(data?.summary?.seeded);

  if (airports.length < 6) {
    const seen = new Set(airports.map((a) => a.iata));
    for (const a of OPERATIONAL_SEED.airports) {
      if (!seen.has(a.iata)) airports.push(a);
    }
    seeded = true;
  }
  if (routes.length < 4) {
    const seen = new Set(routes.map((r) => `${r.source_icao}-${r.destination_icao}`));
    for (const r of OPERATIONAL_SEED.routes) {
      const k = `${r.source_icao}-${r.destination_icao}`;
      if (!seen.has(k)) routes.push(r);
    }
    seeded = true;
  }
  if (events.length < 3 && routes.length) {
    events = routes.slice(0, 8).map((r, i) => ({
      id: `cli-evt-${i}`,
      companhia: r.source_icao,
      tipo_evento: "route_density",
      prioridade: Number(r.risk_score) >= 0.35 ? "high" : "medium",
      latitude: (Number(r.source_lat) + Number(r.destination_lat)) / 2,
      longitude: (Number(r.source_lng) + Number(r.destination_lng)) / 2,
      score: Number(r.risk_score || 0.2),
    }));
  }

  return {
    airports,
    routes,
    events,
    zones: data?.zones?.features ? data.zones : { type: "FeatureCollection", features: [] },
    summary: {
      ...(data?.summary || {}),
      airport_count: airports.length,
      route_count: routes.length,
      event_count: events.length,
      hub_count: airports.filter((a) => Number(a.hub_score || 0) >= 0.65).length,
      seeded,
    },
  };
}
