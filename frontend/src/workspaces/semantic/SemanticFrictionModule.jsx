import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { FrictionMatrix } from "../../components/FrictionMatrix";

function SemanticFrictionModuleInner() {
  const { t } = useTranslation("semantic");

  const emptyContent = (
    <div className="semantic-empty-runtime semantic-empty-runtime--minimal">
      <p className="semantic-empty-runtime__title">{t("emptyTitle")}</p>
      <p className="semantic-empty-runtime__detail">{t("emptyDetail")}</p>
    </div>
  );

  return (
    <OperationalModuleCard
      className="semantic-friction-module"
      title={t("frictionTitle")}
      subtitle={t("frictionSubtitle")}
      expandable
      defaultExpanded
      bodyClassName="semantic-friction-module__body"
    >
      <FrictionMatrix bare chartMaxHeight={400} emptyContent={emptyContent} />
    </OperationalModuleCard>
  );
}

export const SemanticFrictionModule = memo(SemanticFrictionModuleInner);
