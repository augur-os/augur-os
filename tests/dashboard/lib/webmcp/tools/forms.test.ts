/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import {
  formsDiscoverExecute,
  formsFillExecute,
  formsSubmitExecute,
} from "@/lib/webmcp/tools/forms";
import type { FormField, FormState } from "@/lib/webmcp/types";

// --- Fixtures ---

const FIELDS_PROFILE: FormField[] = [
  { name: "name", type: "string", label: "Full Name", required: true },
  { name: "bio", type: "text", label: "Bio" },
];

const FIELDS_SETTINGS: FormField[] = [
  { name: "theme", type: "enum", label: "Theme", options: ["light", "dark"], required: true },
  { name: "notifications", type: "boolean", label: "Enable Notifications" },
];

function makeForm(
  formId: string,
  pageId: string,
  fields: FormField[],
  values: Record<string, unknown>,
): FormState {
  return {
    formId,
    pageId,
    fields,
    values,
    dirty: false,
    submitting: false,
    lastUpdated: Date.now(),
  };
}

describe("forms.discover", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns empty list when no forms registered", async () => {
    const result = await formsDiscoverExecute({}, registry);
    expect(result.forms).toHaveLength(0);
  });

  it("returns all registered forms", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "Alice", bio: "" }));
    registry.reportForm(makeForm("settings-form", "career-settings", FIELDS_SETTINGS, { theme: "dark", notifications: true }));

    const result = await formsDiscoverExecute({}, registry);
    expect(result.forms).toHaveLength(2);
    const ids = result.forms.map((f) => f.formId);
    expect(ids).toContain("profile-form");
    expect(ids).toContain("settings-form");
  });

  it("maps formId, pageId, fields, and values onto output", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "Bob" }));

    const result = await formsDiscoverExecute({}, registry);
    expect(result.forms).toHaveLength(1);
    const form = result.forms[0];
    expect(form.formId).toBe("profile-form");
    expect(form.pageId).toBe("career-profile");
    expect(form.fields).toEqual(FIELDS_PROFILE);
    expect(form.values).toEqual({ name: "Bob" });
  });

  it("filters by page when page param is provided", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));
    registry.reportForm(makeForm("settings-form", "career-settings", FIELDS_SETTINGS, {}));

    const result = await formsDiscoverExecute({ page: "career-settings" }, registry);
    expect(result.forms).toHaveLength(1);
    expect(result.forms[0].formId).toBe("settings-form");
  });

  it("returns empty list when page filter matches no forms", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const result = await formsDiscoverExecute({ page: "nonexistent-page" }, registry);
    expect(result.forms).toHaveLength(0);
  });

  it("does not include dirty or submitting flags in output", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const result = await formsDiscoverExecute({}, registry);
    const form = result.forms[0] as Record<string, unknown>;
    expect(form.dirty).toBeUndefined();
    expect(form.submitting).toBeUndefined();
  });
});

describe("forms.fill", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns NOT_FOUND when form does not exist", async () => {
    const result = await formsFillExecute({ formId: "nonexistent", fields: { name: "Alice" } }, registry);
    expect(result).toMatchObject({ error: true, code: "NOT_FOUND" });
    expect((result as { message: string }).message).toContain("nonexistent");
  });

  it("returns success with previousValues and newValues on valid fill", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "Alice", bio: "" }));

    const result = await formsFillExecute(
      { formId: "profile-form", fields: { name: "Bob", bio: "Engineer" } },
      registry,
    );
    expect(result).toMatchObject({
      success: true,
      formId: "profile-form",
      previousValues: { name: "Alice", bio: "" },
      newValues: { name: "Bob", bio: "Engineer" },
    });
  });

  it("merges new fields into existing values for newValues", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "Alice", bio: "Old bio" }));

    const result = await formsFillExecute(
      { formId: "profile-form", fields: { name: "Charlie" } },
      registry,
    );
    if ("newValues" in result) {
      // Only updated name; bio stays
      expect(result.newValues).toEqual({ name: "Charlie", bio: "Old bio" });
      // Previous values unchanged
      expect(result.previousValues).toEqual({ name: "Alice", bio: "Old bio" });
    }
  });

  it("triggers onFormFill listeners with the provided fields", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "" }));

    const fillHandler = jest.fn();
    registry.onFormFill("profile-form", fillHandler);

    await formsFillExecute({ formId: "profile-form", fields: { name: "Dave" } }, registry);

    expect(fillHandler).toHaveBeenCalledTimes(1);
    expect(fillHandler).toHaveBeenCalledWith({ name: "Dave" });
  });

  it("does not trigger listeners for a different formId", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));
    registry.reportForm(makeForm("settings-form", "career-settings", FIELDS_SETTINGS, {}));

    const fillHandlerSettings = jest.fn();
    registry.onFormFill("settings-form", fillHandlerSettings);

    await formsFillExecute({ formId: "profile-form", fields: { name: "Eve" } }, registry);

    expect(fillHandlerSettings).not.toHaveBeenCalled();
  });
});

describe("forms.submit", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns NOT_FOUND when form does not exist", async () => {
    const result = await formsSubmitExecute({ formId: "nonexistent" }, registry);
    expect(result).toMatchObject({ error: true, code: "NOT_FOUND" });
    expect((result as { message: string }).message).toContain("nonexistent");
  });

  it("returns success for a registered form", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, { name: "Alice" }));

    const result = await formsSubmitExecute({ formId: "profile-form" }, registry);
    expect(result).toMatchObject({ success: true, formId: "profile-form" });
  });

  it("triggers onFormSubmit listeners", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const submitHandler = jest.fn();
    registry.onFormSubmit("profile-form", submitHandler);

    await formsSubmitExecute({ formId: "profile-form" }, registry);

    expect(submitHandler).toHaveBeenCalledTimes(1);
  });

  it("does not trigger submit listeners for a different formId", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));
    registry.reportForm(makeForm("settings-form", "career-settings", FIELDS_SETTINGS, {}));

    const submitHandlerSettings = jest.fn();
    registry.onFormSubmit("settings-form", submitHandlerSettings);

    await formsSubmitExecute({ formId: "profile-form" }, registry);

    expect(submitHandlerSettings).not.toHaveBeenCalled();
  });

  it("can trigger multiple submit listeners on the same form", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const handler1 = jest.fn();
    const handler2 = jest.fn();
    registry.onFormSubmit("profile-form", handler1);
    registry.onFormSubmit("profile-form", handler2);

    await formsSubmitExecute({ formId: "profile-form" }, registry);

    expect(handler1).toHaveBeenCalledTimes(1);
    expect(handler2).toHaveBeenCalledTimes(1);
  });
});

describe("StateRegistry form lifecycle", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("removes form on removeForm call", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));
    registry.removeForm("profile-form");

    const result = await formsDiscoverExecute({}, registry);
    expect(result.forms).toHaveLength(0);
  });

  it("clears all forms on registry.clear()", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));
    registry.reportForm(makeForm("settings-form", "career-settings", FIELDS_SETTINGS, {}));
    registry.clear();

    const result = await formsDiscoverExecute({}, registry);
    expect(result.forms).toHaveLength(0);
  });

  it("unsubscribes fill listener when unsubscribe fn is called", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const handler = jest.fn();
    const unsub = registry.onFormFill("profile-form", handler);
    unsub();

    await formsFillExecute({ formId: "profile-form", fields: { name: "Test" } }, registry);
    expect(handler).not.toHaveBeenCalled();
  });

  it("unsubscribes submit listener when unsubscribe fn is called", async () => {
    registry.reportForm(makeForm("profile-form", "career-profile", FIELDS_PROFILE, {}));

    const handler = jest.fn();
    const unsub = registry.onFormSubmit("profile-form", handler);
    unsub();

    await formsSubmitExecute({ formId: "profile-form" }, registry);
    expect(handler).not.toHaveBeenCalled();
  });
});
