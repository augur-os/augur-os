import { SetupWidget } from "@/features/setup/SetupWidget";

export const dynamic = "force-dynamic";

// ADR-773: Onboarding is a flow, not a setting. It lives on its own page,
// out of the Settings hub. The sidebar chip and the "Open Setup" links across
// the dashboard point here.
export default function SetupPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <SetupWidget variant="page" />
    </div>
  );
}
