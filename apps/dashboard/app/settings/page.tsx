import { redirect } from "next/navigation";
import GeneralTab from "./tabs/GeneralTab";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{
    tab?: string;
  }>;
}

const LEGACY_TAB_ROUTES: Record<string, string> = {
  general: "/settings",
  // AI & Models
  ai: "/settings/ai",
  providers: "/settings/ai",
  // Integrations
  integrations: "/settings/integrations",
  skills: "/settings/integrations",
  plugins: "/settings/integrations",
  dispatch: "/settings/integrations",
  // Appearance
  appearance: "/settings/appearance",
  layout: "/settings/appearance",
  // Privacy & Security
  privacy: "/settings/privacy",
  security: "/settings/privacy",
  permissions: "/settings/privacy",
};

export default async function SettingsPage(props: PageProps) {
  const searchParams = await props.searchParams;
  const requestedTab = searchParams.tab?.toLowerCase();

  if (requestedTab) {
    const destination = LEGACY_TAB_ROUTES[requestedTab];
    if (destination && destination !== "/settings") {
      redirect(destination);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text-secondary)]">
        Set which apps open your files and review where Augur keeps your data on
        disk.
      </p>
      <GeneralTab />
    </div>
  );
}
