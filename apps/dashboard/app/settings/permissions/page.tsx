import { redirect } from "next/navigation";

// Settings IA cleanup: Permissions merged into the Privacy & Security tab.
export default function SettingsPermissionsRedirect() {
  redirect("/settings/privacy");
}
