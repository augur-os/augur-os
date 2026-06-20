import SecurityTab from "../tabs/SecurityTab";
import PermissionsTab from "../tabs/PermissionsTab";

export const dynamic = "force-dynamic";

export default function SettingsPrivacyPage() {
  return (
    <div className="space-y-10">
      <p className="text-sm text-[var(--text-secondary)]">
        Review AI guardrails and audit history, then validate operating-system
        permissions for any blocked capabilities.
      </p>
      <SecurityTab />
      <PermissionsTab />
    </div>
  );
}
