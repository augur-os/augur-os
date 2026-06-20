"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception for top-level feature wiring
import UnifiedActionsFab from "@/features/components/UnifiedActionsFab";
const FloatingChat = dynamic(
  () => import("@/features/components/FloatingChat"),
  { ssr: false },
);
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception for top-level feature wiring
import DynamicPreviewModal from "@/features/components/DynamicPreviewModal";
import { Toaster } from "sonner";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception for top-level feature wiring
import McpHealthProvider from "@/features/components/McpHealthProvider";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception for top-level feature wiring
import PageActionButtons from "@/features/components/PageActionButtons";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception for top-level feature wiring
import MigrationOverlay from "@/features/components/MigrationOverlay";

export default function GlobalShell() {
  return (
    <>
      <UnifiedActionsFab />
      {/* ADR-036: Full bar is dev-mode only. Operation mode uses chat header + sidebar. */}
      <Suspense fallback={null}>
        <PageActionButtons className="z-[60]" />
      </Suspense>
      <FloatingChat />
      <DynamicPreviewModal />
      <Toaster
        richColors
        position="bottom-left"
        toastOptions={{ className: "mb-[calc(4.5rem+env(safe-area-inset-bottom))] md:mb-4" }}
      />
      <McpHealthProvider />
      <MigrationOverlay />
    </>
  );
}
