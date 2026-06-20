import { Check, Type } from "lucide-react";
import { fontOptions, sizeOptions } from "./types";
import {
  modeButtonClass,
  selectionCardClass,
} from "./ui-helper-classes";
import { SectionHeader } from "./ui-helpers";

/**
 * Typography defaults (font family + size). Theme and color-mode controls live
 * in the top-level Theme & Mode card (ADR-773); keeping them out of here avoids
 * a duplicate set of theme pickers on the Appearance settings page.
 */
export function AppearanceTab({
  fontFamily,
  onFontFamilyChange,
  fontSize,
  onFontSizeChange,
}: {
  fontFamily: string;
  onFontFamilyChange: (family: string) => void;
  fontSize: string;
  onFontSizeChange: (size: string) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <SectionHeader>Font Family</SectionHeader>
        <div className="space-y-0.5 px-1">
          {fontOptions.map((font) => (
            <button type="button"
              key={font.value}
              onClick={() => onFontFamilyChange(font.value)}
              className={`w-full flex items-center justify-between px-2 py-2 rounded-lg border transition-all ${selectionCardClass(
                fontFamily === font.value,
              )}`}
            >
              <div className="flex items-center gap-2">
                <Type className="size-3.5 text-[var(--text-muted)]" />
                <div className="text-left">
                  <div className="text-xs font-medium text-[var(--text-primary)]">
                    {font.label}
                  </div>
                  <div className="text-xs text-[var(--text-muted)]">
                    {font.desc}
                  </div>
                </div>
              </div>
              {fontFamily === font.value && (
                <Check className="size-3.5 text-[var(--accent-primary)] shrink-0" />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <SectionHeader>Font Size</SectionHeader>
        <div className="flex gap-1.5 px-1">
          {sizeOptions.map((size) => (
            <button type="button"
              key={size.value}
              onClick={() => onFontSizeChange(size.value)}
              className={`flex-1 flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg border transition-all text-xs ${modeButtonClass(
                fontSize === size.value,
              )}`}
            >
              <span className="font-medium">{size.label}</span>
              <span className="text-xs text-[var(--text-muted)]">
                {size.size}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
