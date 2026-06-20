import { redirect } from "next/navigation";

// Settings IA cleanup: Layout renamed to the Appearance tab.
export default function SettingsLayoutRedirect() {
  redirect("/settings/appearance");
}
