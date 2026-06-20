"use client";

import {
  useCallback,
  useMemo,
  use,
  useState,
  createContext,
  ReactNode,
} from "react";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception
import KeyboardShortcutsModal from "@/features/components/KeyboardShortcutsModal";

const KeyboardShortcutsContext = createContext<{
  showHelp: () => void;
}>({ showHelp: () => {} });

function useKeyboardShortcutsContext() {
  return use(KeyboardShortcutsContext);
}

export default function KeyboardShortcutsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const showHelp = useCallback(() => setIsModalOpen(true), []);
  const hideHelp = useCallback(() => setIsModalOpen(false), []);
  const contextValue = useMemo(() => ({ showHelp }), [showHelp]);

  // Initialize keyboard shortcuts
  useKeyboardShortcuts([], showHelp);

  return (
    <KeyboardShortcutsContext.Provider value={contextValue}>
      {children}
      <KeyboardShortcutsModal isOpen={isModalOpen} onClose={hideHelp} />
    </KeyboardShortcutsContext.Provider>
  );
}
