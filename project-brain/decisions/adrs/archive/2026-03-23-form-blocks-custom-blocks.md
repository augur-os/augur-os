# Form Blocks, Custom Blocks & Conditional Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unblock the remaining ~53 TSX-to-YAML page migrations by adding modal forms on actions, a custom block type with SKILL.md registry, quick-add dispatch, and conditional block visibility.

**Architecture:** Extend existing block types (`RowAction`, `ActionBarBlock`, `DataTableBlock`) with inline `fields` arrays that trigger a generic `ActionFormModal`. Add `id` and `showIf` to `BlockConfig` for conditional visibility. Extend custom block registry generation to scan SKILL.md `custom_blocks` entries in addition to YAML pages.

**Tech Stack:** TypeScript, React, Next.js, existing home-built UI components (Dialog, Button, Input, Select — no Radix UI), existing `useActionRunner` hook.

**Spec:** `docs/superpowers/specs/2026-03-23-form-blocks-custom-blocks-design.md`

**UI note:** This codebase uses home-built UI components in `apps/dashboard/components/ui/`, NOT shadcn/ui or Radix UI. Available: Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Button, Input, Select (native `<select>` wrapper), Tabs, Badge, Card, Progress, Skeleton. Missing components (Label, Textarea, Switch, Checkbox, RadioGroup) must use plain HTML with Tailwind classes.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/dashboard/lib/plugin-schema/types.ts:380-415` | Modify | Add `file` and `toggle` to `FormField.type` union; add `accept` field |
| `apps/dashboard/lib/blocks/types.ts:42-53` | Modify | Extend `RowAction` with `fields`, `refetch`, `confirmText` |
| `apps/dashboard/lib/blocks/flow-types.ts:5-18` | Modify | Add `id`, `showIf`, `ShowIfExpression` to `BlockConfig` |
| `apps/dashboard/components/blocks/ActionFormModal.tsx` | Create | Generic modal form renderer using existing Dialog/Button/Input/Select |
| `apps/dashboard/components/blocks/types/ActionBarBlock.tsx` | Modify | Read actions from config first, detect `fields` → open modal |
| `apps/dashboard/components/blocks/types/DataTableBlock.tsx:70-72` | Modify | Wire quick-add dispatch to useActionRunner |
| `apps/dashboard/components/blocks/RowActionsCell.tsx` | Modify | Detect `fields` on action → open ActionFormModal |
| `apps/dashboard/components/plugin/ConfigPage.tsx:70-73,156-189` | Modify | Track `blockDataMap`, evaluate `showIf`, exclude hidden blocks from sizes array |
| `apps/dashboard/scripts/generate-tab-registry.ts:824-928` | Modify | Also scan SKILL.md `custom_blocks` entries (components must be in `skills/dashboard/components/`) |

---

### Task 1: Extend FormField with `file` and `toggle` types

**Files:**
- Modify: `apps/dashboard/lib/plugin-schema/types.ts:380-415`
- Test: `tests/dashboard/lib/plugin-schema/form-field-types.test.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/lib/plugin-schema/form-field-types.test.ts`:

```typescript
import type { FormField } from "@/lib/plugin-schema/types";

describe("FormField type extensions", () => {
  it("accepts file type with accept property", () => {
    const field: FormField = {
      name: "upload",
      label: "Upload",
      type: "file",
      required: true,
      accept: [".csv", ".xlsx"],
    };
    expect(field.type).toBe("file");
    expect(field.accept).toEqual([".csv", ".xlsx"]);
  });

  it("accepts toggle type", () => {
    const field: FormField = {
      name: "enabled",
      label: "Enabled",
      type: "toggle",
      defaultValue: false,
    };
    expect(field.type).toBe("toggle");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/lib/plugin-schema/form-field-types.test.ts --no-coverage`
Expected: TypeScript error — `"file"` and `"toggle"` not assignable to `FormField["type"]`

- [ ] **Step 3: Modify FormField**

In `apps/dashboard/lib/plugin-schema/types.ts`, add `"file"` and `"toggle"` to the type union (after `"radio"` on line 395), and add `accept?: string[]` field (after `options` on line 403):

```typescript
  type:
    | "text"
    | "textarea"
    | "number"
    | "date"
    | "datetime"
    | "select"
    | "multiselect"
    | "checkbox"
    | "radio"
    | "file"
    | "toggle";
  // ...existing fields...
  /** Accepted file extensions (for type: "file") */
  accept?: string[];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/lib/plugin-schema/form-field-types.test.ts --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/plugin-schema/types.ts tests/dashboard/lib/plugin-schema/form-field-types.test.ts
git commit -m "feat(blocks): extend FormField with file and toggle types"
```

---

### Task 2: Extend RowAction with `fields`, `refetch`, `confirmText` and BlockConfig with `id`, `showIf`

**Files:**
- Modify: `apps/dashboard/lib/blocks/types.ts:42-53`
- Modify: `apps/dashboard/lib/blocks/flow-types.ts:5-18`
- Test: `tests/dashboard/lib/blocks/action-form-types.test.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/lib/blocks/action-form-types.test.ts`:

```typescript
import type { RowAction } from "@/lib/blocks/types";
import type { BlockConfig, ShowIfExpression } from "@/lib/blocks/flow-types";

describe("Action form type extensions", () => {
  it("RowAction accepts fields array", () => {
    const action: RowAction = {
      id: "edit",
      icon: "Pencil",
      label: "Edit",
      dispatch: "fire",
      fields: [
        { name: "title", label: "Title", type: "text", required: true },
      ],
      refetch: ["stats-block"],
    };
    expect(action.fields).toHaveLength(1);
    expect(action.refetch).toEqual(["stats-block"]);
  });

  it("RowAction accepts confirmText for dangerous actions", () => {
    const action: RowAction = {
      id: "delete",
      icon: "Trash",
      label: "Delete",
      dispatch: "fire",
      confirmText: "DELETE",
      fields: [],
    };
    expect(action.confirmText).toBe("DELETE");
  });

  it("BlockConfig accepts id and showIf", () => {
    const showIf: ShowIfExpression = { blockHasData: "other-block" };
    const config: BlockConfig = {
      type: "stat-grid",
      id: "my-stats",
      showIf,
    };
    expect(config.id).toBe("my-stats");
    expect(config.showIf).toEqual({ blockHasData: "other-block" });
  });

  it("ShowIfExpression supports configFlag", () => {
    const showIf: ShowIfExpression = { configFlag: "dev_mode" };
    const config: BlockConfig = { type: "markdown", showIf };
    expect(config.showIf).toEqual({ configFlag: "dev_mode" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/lib/blocks/action-form-types.test.ts --no-coverage`
Expected: TypeScript error

- [ ] **Step 3: Extend RowAction**

In `apps/dashboard/lib/blocks/types.ts`, add to the `RowAction` interface (after `href_template` on line 52):

```typescript
  /** Form fields — when present, clicking opens ActionFormModal instead of direct dispatch */
  fields?: import("@/lib/plugin-schema/types").FormField[];
  /** Block IDs to refetch after successful form submission */
  refetch?: string[];
  /** Dangerous action guard — user must type this exact string to enable submit */
  confirmText?: string;
```

- [ ] **Step 4: Add `id`, `showIf`, `ShowIfExpression` to flow-types.ts**

In `apps/dashboard/lib/blocks/flow-types.ts`, add before `BlockConfig`:

```typescript
/** showIf expression — controls conditional block visibility */
export type ShowIfExpression =
  | { blockHasData: string }
  | { configFlag: string };
```

Add to `BlockConfig` (after `type` line):

```typescript
  /** Optional block identifier — used by refetch and showIf references */
  id?: string;
```

Add before `[key: string]: unknown`:

```typescript
  /** Conditional visibility — block only renders when expression is truthy */
  showIf?: ShowIfExpression;
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/lib/blocks/action-form-types.test.ts --no-coverage`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/blocks/types.ts apps/dashboard/lib/blocks/flow-types.ts tests/dashboard/lib/blocks/action-form-types.test.ts
git commit -m "feat(blocks): extend RowAction with fields/refetch/confirmText, add id/showIf to BlockConfig"
```

---

### Task 3: Build ActionFormModal component

**Files:**
- Create: `apps/dashboard/components/blocks/ActionFormModal.tsx`
- Test: `tests/dashboard/components/blocks/ActionFormModal.test.tsx`

**UI components used:** Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Button, Input, Select (all from `@/components/ui/`). For textarea, label, checkbox, toggle, radio — use plain HTML with Tailwind (no Radix/shadcn).

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/components/blocks/ActionFormModal.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createQueryWrapper } from "../../helpers/component-test-utils";

const mockRunAction = jest.fn().mockResolvedValue({ type: "success", message: "Done" });
jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: mockRunAction, isExecuting: false }),
}));

import ActionFormModal from "@/components/blocks/ActionFormModal";
import type { FormField } from "@/lib/plugin-schema/types";

const { Wrapper } = createQueryWrapper();

const baseFields: FormField[] = [
  { name: "title", label: "Title", type: "text", required: true },
  { name: "status", label: "Status", type: "select", options: [
    { value: "active", label: "Active" },
    { value: "archived", label: "Archived" },
  ]},
];

describe("ActionFormModal", () => {
  beforeEach(() => { mockRunAction.mockClear(); });

  it("renders form fields from config", () => {
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
  });

  it("validates required fields before submit", async () => {
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(mockRunAction).not.toHaveBeenCalled();
  });

  it("dispatches action with form values on valid submit", async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={onClose}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    await user.type(screen.getByLabelText("Title"), "My Item");
    await user.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "edit-item",
          dispatch: "fire",
          args: expect.objectContaining({ title: "My Item" }),
        }),
      );
    });
  });

  it("disables submit until confirmText matches", async () => {
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="delete-item"
        actionLabel="Delete Item"
        dispatch="fire"
        fields={[]}
        confirmText="DELETE"
      />,
      { wrapper: Wrapper },
    );
    const submitBtn = screen.getByRole("button", { name: /submit/i });
    expect(submitBtn).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/type DELETE/i), "DELETE");
    expect(submitBtn).toBeEnabled();
  });

  it("does not render when open is false", () => {
    const { container } = render(
      <ActionFormModal
        open={false}
        onClose={jest.fn()}
        actionId="test"
        actionLabel="Test"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    expect(container.querySelector("[role='dialog']")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/ActionFormModal.test.tsx --no-coverage`
Expected: FAIL — module not found

- [ ] **Step 3: Implement ActionFormModal**

Create `apps/dashboard/components/blocks/ActionFormModal.tsx`. Use only existing UI components: `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` from `@/components/ui/Dialog`, `Button` from `@/components/ui/Button`, `Input` from `@/components/ui/Input`, `Select` from `@/components/ui/Select`. For label, textarea, checkbox, toggle, radio — use plain HTML elements with Tailwind classes matching the codebase design system (`var(--text-primary)`, `var(--bg-secondary)`, `var(--border-color)`, etc.).

Key implementation details:
- `dispatch` prop typed as `DispatchMode` from `@/lib/actions/types` (not the narrower `RowAction.dispatch` — avoids type mismatch when calling `runAction`)
- `normalizeOptions()` handles both `string[]` and `SelectOption[]` since YAML may pass raw strings
- `validateField()` checks `required`, `validation.min/max/minLength/maxLength/pattern`
- `confirmText` renders a separate input below the form that disables submit until exact match
- `onSuccess` callback fires after successful dispatch (for refetch wiring)
- All `<label>` elements use `htmlFor` matching the field's `id` attribute for accessibility

The `Select` component is a native `<select>` wrapper — render it with `<Select>` and `<option>` children (not Radix SelectContent/SelectItem).

Toggle: `<button role="switch" aria-checked>` with Tailwind bg toggle.
Checkbox: `<input type="checkbox">` with Tailwind styling.
Radio: `<fieldset>` + `<input type="radio">` per option.
Textarea: `<textarea>` with Tailwind classes matching Input style.

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/ActionFormModal.test.tsx --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/blocks/ActionFormModal.tsx tests/dashboard/components/blocks/ActionFormModal.test.tsx
git commit -m "feat(blocks): add ActionFormModal — generic modal form for block actions"
```

---

### Task 4: Wire RowActionsCell to open ActionFormModal when action has `fields`

**Files:**
- Modify: `apps/dashboard/components/blocks/RowActionsCell.tsx`
- Test: `tests/dashboard/components/blocks/RowActionsCell-modal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/components/blocks/RowActionsCell-modal.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { createQueryWrapper } from "../../helpers/component-test-utils";

const mockRunAction = jest.fn().mockResolvedValue({ type: "success", message: "Done" });
jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: mockRunAction, isExecuting: false }),
}));

import RowActionsCell from "@/components/blocks/RowActionsCell";

const { Wrapper } = createQueryWrapper();

describe("RowActionsCell with fields", () => {
  beforeEach(() => { mockRunAction.mockClear(); });

  it("opens ActionFormModal when action has fields", async () => {
    render(
      <RowActionsCell
        actions={[
          {
            id: "edit",
            icon: "Pencil",
            label: "Edit",
            dispatch: "fire",
            fields: [
              { name: "title", label: "Title", type: "text" as const, required: true },
            ],
          },
        ]}
        row={{ id: "1", title: "Test" }}
      />,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByTitle("Edit"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });

  it("dispatches directly when action has no fields", () => {
    render(
      <RowActionsCell
        actions={[
          { id: "delete", icon: "Trash", label: "Delete", dispatch: "fire" },
        ]}
        row={{ id: "1" }}
      />,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByTitle("Delete"));
    expect(mockRunAction).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/RowActionsCell-modal.test.tsx --no-coverage`
Expected: FAIL

- [ ] **Step 3: Modify RowActionsCell**

In `apps/dashboard/components/blocks/RowActionsCell.tsx`:

1. Add import: `import ActionFormModal from "./ActionFormModal";`
2. Add state inside component: `const [formAction, setFormAction] = useState<{ action: RowAction; payload: Record<string, unknown> } | null>(null);`
3. In `dispatchAction` callback, before `executeAction(action, payload)`, add:

```typescript
if (action.fields && action.fields.length > 0) {
  setFormAction({ action, payload });
  return;
}
```

4. Before the closing `</>`, add:

```tsx
{formAction?.action.fields && (
  <ActionFormModal
    open={formAction !== null}
    onClose={() => setFormAction(null)}
    actionId={formAction.action.id}
    actionLabel={formAction.action.label}
    dispatch={formAction.action.dispatch === "navigate" ? "fire" : formAction.action.dispatch}
    fields={formAction.action.fields}
    staticArgs={formAction.payload}
    mcpTool={formAction.action.mcp_tool ?? mcpTool}
    confirmText={formAction.action.confirmText}
    refetch={formAction.action.refetch}
  />
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/RowActionsCell-modal.test.tsx --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/blocks/RowActionsCell.tsx tests/dashboard/components/blocks/RowActionsCell-modal.test.tsx
git commit -m "feat(blocks): RowActionsCell opens ActionFormModal when action has fields"
```

---

### Task 5: Refactor ActionBarBlock to read config actions + support fields

**Files:**
- Modify: `apps/dashboard/components/blocks/types/ActionBarBlock.tsx`
- Modify: `tests/dashboard/components/blocks/types/block-types.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `tests/dashboard/components/blocks/types/block-types.test.tsx` (import `fireEvent, screen` at top):

```tsx
describe("ActionBarBlock config actions", () => {
  it("renders actions from config.actions when no MCP data", async () => {
    const mod = await import("@/components/blocks/types/ActionBarBlock");
    const ActionBarBlock = mod.default;
    render(
      <ActionBarBlock
        instanceId="test-ab"
        config={{
          title: "Actions",
          actions: [
            { id: "run", label: "Run Task", dispatch: "fire" },
          ],
        }}
        mode="compact"
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("Run Task")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/types/block-types.test.tsx -t "config actions" --no-coverage`
Expected: FAIL — ActionBarBlock only reads from MCP data

- [ ] **Step 3: Refactor ActionBarBlock**

Rewrite `apps/dashboard/components/blocks/types/ActionBarBlock.tsx` to:
- Define `ConfigAction` interface with `id`, `label`, `icon?`, `dispatch?`, `mcp_tool?`, `fields?`, `confirmText?`, `refetch?`
- Read `config.actions` (config-declared from YAML) as primary source
- Fall back to MCP-fetched data as secondary source
- When an action has `fields`, open `ActionFormModal` instead of direct dispatch
- `dispatch` defaults to `"ide"` for MCP-fetched actions, uses action's declared dispatch for config actions

See the current file at `apps/dashboard/components/blocks/types/ActionBarBlock.tsx` for the existing structure to preserve (BlockShell wrapper, loading skeletons, error states).

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/types/block-types.test.tsx --no-coverage`
Expected: All tests PASS including the new one

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/blocks/types/ActionBarBlock.tsx tests/dashboard/components/blocks/types/block-types.test.tsx
git commit -m "feat(blocks): ActionBarBlock reads config actions, supports modal forms via fields"
```

---

### Task 6: Wire quick-add dispatch in DataTableBlock

**Files:**
- Modify: `apps/dashboard/components/blocks/types/DataTableBlock.tsx:70-72`

- [ ] **Step 1: Add useActionRunner import and hook call**

In `apps/dashboard/components/blocks/types/DataTableBlock.tsx`:

1. Add import: `import { useActionRunner } from "@/hooks/useActionRunner";`
2. Inside `DataTableBlock`, add: `const { runAction } = useActionRunner();`
3. Replace lines 70-72 with:

```typescript
const handleQuickAddSubmit = useCallback(async (values: Record<string, string>) => {
  if (!props.quickAdd?.action) return;
  await runAction({
    id: props.quickAdd.action,
    label: "Add item",
    description: "Add item via quick-add",
    dispatch: "fire",
    page: typeof window !== "undefined" ? window.location.pathname : "",
    args: values,
  });
}, [props.quickAdd?.action, runAction]);
```

- [ ] **Step 2: Run existing block tests to verify no regressions**

Run: `pnpm --filter dashboard jest tests/dashboard/components/blocks/types/block-types.test.tsx --no-coverage`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/blocks/types/DataTableBlock.tsx
git commit -m "fix(blocks): wire quick-add dispatch to useActionRunner (resolves TODO_BUG)"
```

---

### Task 7: Add conditional block visibility (showIf) to ConfigPage

**Files:**
- Modify: `apps/dashboard/components/plugin/ConfigPage.tsx`
- Test: `tests/dashboard/components/plugin/ConfigPage-showIf.test.tsx`

**Design:** All blocks render (including hidden ones), but `FlowBlockRenderer` returns `null` when `showIf` fails. A shared `BlockDataMap` context lets blocks report their data status and other blocks read it. The `ConfigPage` computes `sizes` and `children` arrays, then filters out hidden blocks from both arrays simultaneously so `FlowLayout` never sees gaps.

**Implementation approach:**
1. Create `BlockDataMapContext` and `ReportBlockDataContext` inside `ConfigPage.tsx`
2. `FlowBlockRenderer` reports data status via `useEffect` when it has a block `id`
3. `FlowBlockRenderer` evaluates `showIf` against `blockDataMap` and page-level config (passed via prop, not from block config)
4. `ConfigPage` wraps children in providers, and filters the `sizes` + `children` arrays together using a render-phase filter that checks `showIf` against the current `blockDataMap`

**Note on `configFlag`:** The expression `{ configFlag: "flag_name" }` reads from page-level YAML fields, not block fields. Pass the page config's top-level fields as a `pageFlags` prop to `FlowBlockRenderer`.

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/components/plugin/ConfigPage-showIf.test.tsx`. Mock `useBlockData` to control which blocks return data. Verify that blocks with `showIf: { blockHasData: "some-id" }` are hidden when the referenced block has no data, and shown when it does. Verify blocks without `showIf` always render.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter dashboard jest tests/dashboard/components/plugin/ConfigPage-showIf.test.tsx --no-coverage`
Expected: FAIL

- [ ] **Step 3: Implement showIf**

In `apps/dashboard/components/plugin/ConfigPage.tsx`:

1. Add `ShowIfExpression` to the flow-types import
2. Add `createContext, useContext, useEffect` to React imports
3. Create contexts:

```typescript
type BlockDataMap = Record<string, boolean>;
const BlockDataMapCtx = createContext<BlockDataMap>({});
const ReportBlockDataCtx = createContext<(id: string, hasData: boolean) => void>(() => {});
```

4. In `ConfigPage`, add state and callback:

```typescript
const [blockDataMap, setBlockDataMap] = useState<BlockDataMap>({});
const reportBlockData = useCallback((blockId: string, hasData: boolean) => {
  setBlockDataMap((prev) => prev[blockId] === hasData ? prev : { ...prev, [blockId]: hasData });
}, []);
```

5. Wrap the FlowLayout in providers
6. In `FlowBlockRenderer`, destructure `id` and `showIf` out of block:

```typescript
const { type, mcp_tool, component, size, scope, skill_id, manifest_id,
        search, filters, row_actions, config_schema, id: blockId, showIf, ...rest } = block;
```

7. After `useBlockData`, report data status:

```typescript
const reportBlockData = useContext(ReportBlockDataCtx);
const blockDataMapCtx = useContext(BlockDataMapCtx);

useEffect(() => {
  if (blockId) {
    const hasData = data != null && (Array.isArray(data) ? data.length > 0 : typeof data === "object" ? Object.keys(data).length > 0 : true);
    reportBlockData(blockId, hasData);
  }
}, [blockId, data, reportBlockData]);
```

8. Evaluate showIf:

```typescript
if (showIf) {
  if ("blockHasData" in showIf && !blockDataMapCtx[showIf.blockHasData]) return null;
  if ("configFlag" in showIf && !pageFlags?.[showIf.configFlag]) return null;
}
```

9. In `ConfigPage`, filter sizes and children together: use `useMemo` to pair blocks with their indices, then after rendering, filter out null children. Alternatively, use the simpler approach of passing showIf to FlowLayout and having it skip null children — check if FlowLayout already handles null children. If not, filter in the children/sizes map step.

Read `apps/dashboard/lib/blocks/flow-layout.tsx` to check if FlowLayout filters nulls. If it does, just let FlowBlockRenderer return null. If not, add null filtering to FlowLayout or filter both arrays in ConfigPage.

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter dashboard jest tests/dashboard/components/plugin/ConfigPage-showIf.test.tsx --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/plugin/ConfigPage.tsx tests/dashboard/components/plugin/ConfigPage-showIf.test.tsx
git commit -m "feat(blocks): add showIf conditional visibility to ConfigPage blocks"
```

---

### Task 8: Extend custom block registry to scan SKILL.md entries

**Files:**
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts:824-928`

- [ ] **Step 1: Modify generateCustomBlockRegistry**

In `generateCustomBlockRegistry()`, after the YAML page scan loop (around line 880), add a second scan that:
1. Reads all `skills/*/SKILL.md` files
2. Extracts YAML frontmatter
3. Looks for `x-augur-config.contributions.custom_blocks[]`
4. For each entry, validates `component` field exists and the file exists at `skills/dashboard/components/{Component}.tsx` (since `@skill/` maps to `skills/dashboard/`)
5. Adds to `customComponents` map

**Note:** All custom block components must live in `skills/dashboard/components/` because the `@skill/` alias maps to `skills/dashboard/`. Components in `skills/{other-skill}/augur/dashboard/components/` cannot be imported via `@skill/` today. The script should warn if a SKILL.md references a component that only exists in the skill's own directory.

- [ ] **Step 2: Run the generator to verify no regressions**

Run: `pnpm --filter dashboard run generate-registry`
Expected: Completes without errors. `custom-block-registry.ts` unchanged (no skills declare custom_blocks yet).

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/scripts/generate-tab-registry.ts
git commit -m "feat(blocks): extend custom block registry to scan SKILL.md custom_blocks entries"
```

---

### Task 9: Integration test + build verification

**Files:**
- Test: `tests/dashboard/integration/yaml-page-form.test.tsx`

- [ ] **Step 1: Write integration test**

Create `tests/dashboard/integration/yaml-page-form.test.tsx` that renders a `ConfigPage` with a YAML-style page config containing an `action-bar` block with `fields` on one of its actions. Verify:
1. Action button renders
2. Clicking it opens the form modal
3. Filling out the form and submitting calls `runAction` with correct args

Mock `useActionRunner` and `useBlockData`.

- [ ] **Step 2: Run integration test**

Run: `pnpm --filter dashboard jest tests/dashboard/integration/yaml-page-form.test.tsx --no-coverage`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pnpm --filter dashboard jest --no-coverage`
Expected: All tests PASS

- [ ] **Step 4: Run dashboard build**

Run: `pnpm --filter dashboard build`
Expected: Build succeeds with no type errors

- [ ] **Step 5: Commit test**

```bash
git add tests/dashboard/integration/yaml-page-form.test.tsx
git commit -m "test(blocks): integration test for YAML page with modal form"
```
