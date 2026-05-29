const TZ = "America/Sao_Paulo";

const timeFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});

const dateFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ, day: "2-digit", month: "short", year: "numeric",
});

const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ, day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});

const shortDateFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric",
});

function toDate(input) {
  if (!input) return null;
  if (input instanceof Date) return input;
  const d = new Date(input);
  return isNaN(d.getTime()) ? null : d;
}

export function formatOperationalTime(input) {
  const d = toDate(input) || new Date();
  return timeFmt.format(d);
}

export function formatOperationalDate(input) {
  const d = toDate(input);
  if (!d) return "—";
  return dateFmt.format(d).toUpperCase();
}

export function formatOperationalDateTime(input) {
  const d = toDate(input);
  if (!d) return "—";
  const parts = dateTimeFmt.formatToParts(d);
  const get = (type) => (parts.find((p) => p.type === type) || {}).value || "";
  return `${get("day")} ${get("month").toUpperCase()} ${get("year")} • ${get("hour")}:${get("minute")}:${get("second")}`;
}

export function formatShortDate(input) {
  const d = toDate(input);
  if (!d) return "—";
  return shortDateFmt.format(d);
}

export function toBrasiliaISO(input) {
  const d = toDate(input);
  if (!d) return null;
  return d.toLocaleString("sv-SE", { timeZone: TZ }).replace(" ", "T");
}

export function brasiliaTime() {
  return timeFmt.format(new Date());
}

export function operationalRelative(input, locale = "pt") {
  const d = toDate(input);
  if (!d) return "—";
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (locale === "pt") {
    if (secs < 5) return "agora";
    if (secs < 60) return `há ${secs}s`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `há ${mins}min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `há ${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `há ${days}d`;
  }
  if (secs < 5) return "now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export const OPERATIONAL_TZ_LABEL = "BRT";
