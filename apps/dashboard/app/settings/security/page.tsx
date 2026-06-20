import { redirect } from "next/navigation";

// Settings IA cleanup: Security merged into the Privacy & Security tab.
export default function SettingsSecurityRedirect() {
  redirect("/settings/privacy");
}
