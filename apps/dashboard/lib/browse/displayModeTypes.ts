// Leaf module: shared display-mode type with no dependencies, so both
// types.ts and displayMode.ts can import it without forming an import cycle.
export type BrowseDisplayMode = "card" | "list";
