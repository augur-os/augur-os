"use client";

import { useSecurityTabController } from "./SecurityTab.controller";
import { AiGuardrailsSection } from "./SecurityTab.guardrails";
import { CodebaseSecurityAuditSection } from "./SecurityTab.audit";
import { AuditLogSection } from "./SecurityTab.log";

export default function SecurityTab() {
  const controller = useSecurityTabController();

  return (
    <div className="space-y-8 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-500">
      <AiGuardrailsSection controller={controller} />
      <CodebaseSecurityAuditSection controller={controller} />
      <AuditLogSection controller={controller} />
    </div>
  );
}
