import { redirect } from "next/navigation";

// Settings IA cleanup: Providers merged into the AI & Models tab.
export default function SettingsProvidersRedirect() {
  redirect("/settings/ai");
}
