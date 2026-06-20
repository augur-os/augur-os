/**
 * Login page layout — renders WITHOUT the dashboard shell (no sidebar, no header).
 * The login page is a standalone full-screen form.
 */
export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
