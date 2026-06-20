import type { ModelContext } from "../types";
import type {
  FormsDiscoverInput,
  FormsDiscoverOutput,
  FormsFillInput,
  FormsFillOutput,
  FormsSubmitInput,
  FormsSubmitOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { mcpError } from "./errors";

// --- Exported execute functions (testable without navigator.modelContext) ---

export async function formsDiscoverExecute(
  input: FormsDiscoverInput,
  registry: StateRegistry,
): Promise<FormsDiscoverOutput> {
  let forms = registry.getAllForms().map((f) => ({
    formId: f.formId,
    pageId: f.pageId,
    fields: f.fields,
    values: f.values,
  }));
  if (input.page) forms = forms.filter((f) => f.pageId === input.page);
  return { forms };
}

export async function formsFillExecute(
  input: FormsFillInput,
  registry: StateRegistry,
): Promise<FormsFillOutput | WebMCPError> {
  const form = registry.getForm(input.formId);
  if (!form) return mcpError("NOT_FOUND", `Form "${input.formId}" not found`);
  const previousValues = { ...form.values };
  registry.triggerFormFill(input.formId, input.fields);
  return {
    success: true,
    formId: input.formId,
    previousValues,
    newValues: { ...previousValues, ...input.fields },
  };
}

export async function formsSubmitExecute(
  input: FormsSubmitInput,
  registry: StateRegistry,
): Promise<FormsSubmitOutput | WebMCPError> {
  const form = registry.getForm(input.formId);
  if (!form) return mcpError("NOT_FOUND", `Form "${input.formId}" not found`);
  registry.triggerFormSubmit(input.formId);
  return { success: true, formId: input.formId };
}

// --- Tool registration ---

export function registerFormTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "forms.discover",
    description:
      "List all registered forms in the dashboard. Forms must opt in via useWebMCPForm. Returns form IDs, field definitions, and current values. Filter by pageId to narrow results.",
    inputSchema: {
      type: "object",
      properties: {
        page: {
          type: "string",
          description: "Filter by pageId (e.g., 'career-settings') to list forms on a specific page",
        },
      },
    },
    execute: async (input) => formsDiscoverExecute(input as FormsDiscoverInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "forms.fill",
    description:
      "Fill one or more fields in a registered form. Triggers the onFill callback in the form component, which should update the component's state. Returns previous and new field values.",
    inputSchema: {
      type: "object",
      properties: {
        formId: { type: "string", description: "ID of the form to fill" },
        fields: {
          type: "object",
          description: "Map of field names to new values",
        },
      },
      required: ["formId", "fields"],
    },
    execute: async (input) => formsFillExecute(input as FormsFillInput, registry),
    annotations: { readOnlyHint: false },
  });

  mc.registerTool({
    name: "forms.submit",
    description:
      "Submit a registered form. Triggers the onSubmit callback in the form component. The component is responsible for handling validation and the actual submit logic.",
    inputSchema: {
      type: "object",
      properties: {
        formId: { type: "string", description: "ID of the form to submit" },
      },
      required: ["formId"],
    },
    execute: async (input) => formsSubmitExecute(input as FormsSubmitInput, registry),
    annotations: { readOnlyHint: false },
  });
}
