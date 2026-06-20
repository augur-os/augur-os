import ProvidersPage from "@/features/pages/settings/providers/ProvidersPage";
import LocalBackendSection from "../components/LocalBackendSection";
import { AiActivitySection } from "../components/AiActivitySection";

export const dynamic = "force-dynamic";

export default function SettingsAiPage() {
  return (
    <div className="space-y-10">
      <p className="text-sm text-[var(--text-secondary)]">
        Manage the system LLM, remote provider credentials and budgets, and the
        local Ollama backend for AI execution.
      </p>

      {/* Configure zone: everything you set */}
      <ProvidersPage />
      <LocalBackendSection />

      {/* Activity & status zone: read-only (ADR-773) */}
      <AiActivitySection />
    </div>
  );
}
