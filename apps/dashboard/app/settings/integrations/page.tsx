import McpControlPanel from "../tabs/McpControlPanel";
import DispatchTargetsTab from "../tabs/DispatchTargetsTab";

export const dynamic = "force-dynamic";

export default function SettingsIntegrationsPage() {
  return (
    <div className="space-y-10">
      <p className="text-sm text-[var(--text-secondary)]">
        Connections to your AI clients and tools: MCP server configuration
        and dispatch targets.
      </p>

      <McpControlPanel />

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Dispatch Targets
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Enable or disable dispatch target groups and configure which variants
            are available for action execution.
          </p>
        </div>
        <DispatchTargetsTab />
      </section>
    </div>
  );
}
