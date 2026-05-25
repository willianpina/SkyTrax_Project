import React from "react";
import { useTranslation } from "react-i18next";
import { Globe, Map, Layers } from "lucide-react";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { PanelShell } from "../../components/ui/PanelShell";

export default function GeospatialWorkspace() {
  const { t } = useTranslation(["command", "nav"]);

  return (
    <WorkspaceShell id="geospatial" title={t("nav:nav.geospatial")} subtitle={t("command:map.subtitle")} accent="signal">
      <PanelShell title={t("command:map.title")} subtitle={t("command:map.subtitle")} accent="signal">
        <div className="geo-workspace-content">
          <article className="geo-map-area glass-panel">
            <div className="map-layers">
              {["routes", "risk", "coverage", "alerts"].map((layer) => (
                <span className="map-layer-chip" key={layer}>
                  <span className="map-layer-dot" aria-hidden />
                  {t(`command:map.layers.${layer}`)}
                </span>
              ))}
            </div>
            <div className="map-grid-placeholder geo-large">
              <div className="map-scan" aria-hidden />
              <Globe size={48} className="geo-icon" />
              <p>{t("command:map.placeholder")}</p>
            </div>
          </article>

          <div className="geo-sidebar">
            <div className="geo-info-card glass-panel">
              <Map size={16} className="muted-icon" />
              <h3>{t("nav:geo.hubsTitle", { defaultValue: "Hub intelligence" })}</h3>
              <p className="muted-copy">{t("nav:geo.hubsDesc", { defaultValue: "Connect PostGIS for live hub and route intelligence overlays." })}</p>
            </div>
            <div className="geo-info-card glass-panel">
              <Layers size={16} className="muted-icon" />
              <h3>{t("nav:geo.layersTitle", { defaultValue: "Map layers" })}</h3>
              <p className="muted-copy">{t("nav:geo.layersDesc", { defaultValue: "Prepared for Deck.gl / Mapbox integration. Currently in lightweight mode." })}</p>
            </div>
          </div>
        </div>
      </PanelShell>
    </WorkspaceShell>
  );
}
