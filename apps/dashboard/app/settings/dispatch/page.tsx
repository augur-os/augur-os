import { redirect } from "next/navigation";

// Settings IA cleanup: Dispatch merged into the Integrations tab.
export default function SettingsDispatchRedirect() {
  redirect("/settings/integrations");
}
