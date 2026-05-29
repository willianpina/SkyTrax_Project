import React from "react";
import { AlertTriangle, CheckCircle2, Circle, Clock3, Radar } from "lucide-react";

function iconFor(level) {
  if (level === "error") return AlertTriangle;
  if (level === "success") return CheckCircle2;
  if (level === "active") return Radar;
  if (level === "warning") return Clock3;
  return Circle;
}

export function TimelinePanel({ events = [], title = "Operational events", maxRows = 14 }) {
  const sliced = events.slice(-maxRows);
  return (
    <section className="sods-timeline-panel">
      <header className="sods-timeline-panel__head">
        <h4>{title}</h4>
        <span className="sods-tabular">{events.length}</span>
      </header>
      <div className="sods-timeline" role="list">
        {sliced.map((event, idx) => {
          const Icon = iconFor(event.level);
          return (
            <div className="sods-timeline__row" role="listitem" key={event.id || idx}>
              <Icon size={10} className={`sods-timeline__icon sods-timeline__icon--${event.level || "neutral"}`} />
              <time className="sods-timeline__time sods-tabular">{event.time || "--:--:--"}</time>
              <span className="sods-timeline__message">{event.message}</span>
              <span className="sods-timeline__duration sods-tabular">{event.duration || ""}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
