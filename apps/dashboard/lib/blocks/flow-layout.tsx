"use client";

import { isValidElement, type ReactNode } from "react";
import { SIZE_FRACTIONS, type BlockSize } from "./flow-types";

interface FlowLayoutProps {
  children: ReactNode[];
  sizes: BlockSize[];
}

interface Row {
  key: string;
  items: { key: string; child: ReactNode; size: BlockSize }[];
}

/** Group children into rows based on size fractions (auto-flow algorithm). */
function buildRows(children: ReactNode[], sizes: BlockSize[]): Row[] {
  const rows: Row[] = [];
  let currentItems: Row["items"] = [];
  let remaining = 1.0;
  let fallbackKeyCounter = 0;

  const flushRow = () => {
    if (currentItems.length === 0) return;
    rows.push({
      key: currentItems.map((item) => item.key).join("|"),
      items: currentItems,
    });
    currentItems = [];
    remaining = 1.0;
  };

  for (let i = 0; i < children.length; i++) {
    // Skip null/undefined children (e.g. hidden by showIf)
    const child = children[i];
    if (child == null) continue;

    const size = sizes[i] ?? "full";
    const fraction = SIZE_FRACTIONS[size];
    const key =
      isValidElement(child) && child.key != null
        ? String(child.key)
        : `flow-item-${fallbackKeyCounter++}`;

    if (fraction > remaining + 0.001) {
      // Current row is full — push it and start a new one
      flushRow();
    }

    currentItems.push({ key, child, size });
    remaining -= fraction;

    // If row is (approximately) full, flush it
    if (remaining < 0.001) {
      flushRow();
    }
  }

  // Push any remaining items
  flushRow();

  return rows;
}

/** Gap between items is gap-4 = 1rem. For N items sharing a row, each item
 *  needs to give up (N-1)/N of the gap. half → 2 items, third → 3. */
const GAP_COMPENSATION: Record<BlockSize, string> = {
  full: "0px",
  half: "0.5rem",   // 1 gap shared by 2 items
  third: "0.6667rem", // 2 gaps shared by 3 items
};

function sizeToCalc(size: BlockSize): string {
  const pct = (SIZE_FRACTIONS[size] * 100).toFixed(4);
  const comp = GAP_COMPENSATION[size];
  if (comp === "0px") return `${pct}%`;
  return `calc(${pct}% - ${comp})`;
}

/**
 * FlowLayout — auto-flows children into rows based on declared sizes.
 *
 * Blocks declare `size: full | half | third` and the layout packs them
 * into rows automatically. No grid coordinates needed.
 *
 * Responsive: below `md` breakpoint, all blocks become full-width.
 */
export function FlowLayout({ children, sizes }: FlowLayoutProps) {
  if (!children || children.length === 0) return null;

  const rows = buildRows(children, sizes);

  return (
    <div className="flex flex-col gap-4" data-testid="flow-layout">
      {rows.map((row) => (
        <div key={row.key} className="flex flex-row flex-wrap gap-4" data-testid="flow-row">
          {row.items.map((item) => {
            const calc = sizeToCalc(item.size);
            return (
              <div
                key={item.key}
                className="min-w-0 md:flex-none flex-none w-full"
                style={{ flexBasis: calc, maxWidth: calc }}
                data-testid="flow-cell"
                data-size={item.size}
              >
                {item.child}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
