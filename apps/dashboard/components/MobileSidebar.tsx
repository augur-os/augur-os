"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import SidebarNav from "./SidebarNav";
import BrainLogo from "./BrainLogo";

export default function MobileSidebar() {
  const pathname = usePathname();

  return <MobileSidebarContent key={pathname ?? ""} />;
}

function MobileSidebarContent() {
  const [isOpen, setIsOpen] = useState(false);

  // Close sidebar on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  // Prevent body scroll when sidebar is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  return (
    <>
      {/* Mobile Header with Hamburger */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 liquid-glass border-b border-[var(--border-color)] flex items-center justify-between px-4">
        <BrainLogo />
        <div className="flex min-w-0 items-center gap-2">
          <button type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="p-2 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors"
            aria-label={isOpen ? "Close menu" : "Open menu"}
            aria-expanded={isOpen}
          >
            {isOpen ? <X className="size-6" /> : <Menu className="size-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Sidebar Overlay — z-45 sits between header (z-40) and drawer (z-50) */}
      {isOpen && (
        <button
          type="button"
          aria-label="Close menu overlay"
          className="md:hidden fixed inset-0 bg-black/50 z-[45] backdrop-blur-sm border-0 p-0"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Mobile Sidebar Drawer */}
      <aside
        className={`md:hidden fixed top-14 left-0 bottom-0 w-64 z-50 bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] transform transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-4 flex flex-col gap-4 h-full overflow-y-auto">
          <SidebarNav onNavigate={() => setIsOpen(false)} />
        </div>
      </aside>

      {/* Spacer for mobile header */}
      <div className="md:hidden h-14" />
    </>
  );
}
