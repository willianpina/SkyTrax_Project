/** Temporary cross-layer audit logs (filter console by [AVIATION], [HUBS], etc.). */

export function logDomain(domain, { endpoint = "", recordsLoaded, recordsReturned, recordsRendered, extra } = {}) {
  const tag = String(domain || "AVIATION").toUpperCase();
  const payload = {
    endpoint: endpoint || undefined,
    records_loaded: recordsLoaded,
    records_returned: recordsReturned,
    records_rendered: recordsRendered,
    ...extra,
  };
  Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
  console.info(`[${tag}]`, payload);
}
