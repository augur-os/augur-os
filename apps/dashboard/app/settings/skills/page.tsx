import { redirect } from "next/navigation";

// Settings IA cleanup: Plugins merged into the Integrations tab.
export default function SettingsSkillsRedirect() {
  redirect("/settings/integrations");
}
