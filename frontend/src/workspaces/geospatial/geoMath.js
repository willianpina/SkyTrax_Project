/** Great-circle interpolation for TripsLayer paths */
export function interpolateGreatCircle([lng1, lat1], [lng2, lat2], steps = 24) {
  const toRad = (d) => (d * Math.PI) / 180;
  const toDeg = (r) => (r * 180) / Math.PI;

  const φ1 = toRad(lat1);
  const λ1 = toRad(lng1);
  const φ2 = toRad(lat2);
  const λ2 = toRad(lng2);

  const Δ =
    2 *
    Math.asin(
      Math.sqrt(
        Math.sin((φ2 - φ1) / 2) ** 2 +
          Math.cos(φ1) * Math.cos(φ2) * Math.sin((λ2 - λ1) / 2) ** 2,
      ),
    );

  if (Δ < 1e-8) {
    return [[lng1, lat1], [lng2, lat2]];
  }

  const path = [];
  for (let i = 0; i <= steps; i += 1) {
    const f = i / steps;
    const A = Math.sin((1 - f) * Δ) / Math.sin(Δ);
    const B = Math.sin(f * Δ) / Math.sin(Δ);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1) + B * Math.sin(φ2);
    const φ = Math.atan2(z, Math.sqrt(x * x + y * y));
    const λ = Math.atan2(y, x);
    path.push([toDeg(λ), toDeg(φ)]);
  }
  return path;
}

export function buildTripsFromRoutes(routes, { maxTrips = 96, steps = 28, stepMs = 40 } = {}) {
  const trips = [];
  for (const route of routes.slice(0, maxTrips)) {
    const slng = Number(route.source_lng);
    const slat = Number(route.source_lat);
    const dlng = Number(route.destination_lng);
    const dlat = Number(route.destination_lat);
    if (![slng, slat, dlng, dlat].every(Number.isFinite)) continue;

    const path = interpolateGreatCircle([slng, slat], [dlng, dlat], steps);
    const timestamps = path.map((_, i) => i * stepMs);
    trips.push({
      path,
      timestamps,
      vendor: trips.length % 12,
      risk: Number(route.risk_score || 0),
    });
  }
  return trips;
}

export function tripAnimationBounds(trips) {
  if (!trips.length) return { loopMs: 1200, maxMs: 1200 };
  const maxMs = Math.max(...trips.map((t) => t.timestamps[t.timestamps.length - 1] || 0), 1);
  return { loopMs: maxMs + 400, maxMs };
}
