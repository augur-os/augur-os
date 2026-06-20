"use client";

import { useCallback, useEffect, useReducer } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { mcpCall } from "@/lib/mcp/client";
import { AlertCircle, Cpu, Loader2, Plane, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";

interface LocalBackendModel {
  name?: string;
  size?: string;
  modified?: string;
}

interface LocalBackendStatus {
  ollama?: {
    installed?: boolean;
    version?: string | null;
    binary?: string | null;
    server_running?: boolean;
    models?: LocalBackendModel[];
    configured_model?: string;
    configured_agent?: string;
    has_configured_model?: boolean;
    ready?: boolean;
  };
}

interface OllamaIntegrations {
  integrations?: string[];
}

interface PreferenceWriteResult {
  success?: boolean;
  error?: string;
  details?: string;
  message?: string;
}

type TestConnectionResult =
  | { status: "ready"; message: string }
  | { status: "not-ready"; message: string }
  | { status: "error"; message: string };

interface LocalBackendUiState {
  airplaneUpdating: boolean;
  airplaneToggleError: string | null;
  selectedLocalModel: string;
  modelUpdateError: string | null;
  modelUpdating: boolean;
  testingLocalBackend: boolean;
  localBackendMounted: boolean;
  testConnectionResult: TestConnectionResult | null;
}

type LocalBackendAction =
  | { type: "set-mounted" }
  | { type: "sync-selected-model"; model: string }
  | { type: "airplane-start" }
  | { type: "airplane-error"; error: string }
  | { type: "airplane-finish" }
  | { type: "model-start"; model: string }
  | { type: "model-success" }
  | { type: "model-error"; previousModel: string; error: string }
  | { type: "test-start" }
  | { type: "test-result"; result: TestConnectionResult }
  | { type: "test-finish" };

const INITIAL_LOCAL_BACKEND_STATE: LocalBackendUiState = {
  airplaneUpdating: false,
  airplaneToggleError: null,
  selectedLocalModel: "",
  modelUpdateError: null,
  modelUpdating: false,
  testingLocalBackend: false,
  localBackendMounted: false,
  testConnectionResult: null,
};

const UNSUPPORTED_LOCAL_BACKEND_AGENTS = ["gemini", "cursor-cli"];
const UNSUPPORTED_LOCAL_BACKEND_AGENT_SET = new Set(
  UNSUPPORTED_LOCAL_BACKEND_AGENTS,
);

const CONNECTION_RESULT_STYLES: Record<TestConnectionResult["status"], string> = {
  ready:
    "border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 text-[var(--accent-success)]",
  "not-ready":
    "border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]",
  error:
    "border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)]",
};

function localBackendReducer(
  state: LocalBackendUiState,
  action: LocalBackendAction,
): LocalBackendUiState {
  switch (action.type) {
    case "set-mounted":
      return { ...state, localBackendMounted: true };
    case "sync-selected-model":
      return state.selectedLocalModel === action.model
        ? state
        : { ...state, selectedLocalModel: action.model };
    case "airplane-start":
      return { ...state, airplaneUpdating: true, airplaneToggleError: null };
    case "airplane-error":
      return { ...state, airplaneToggleError: action.error };
    case "airplane-finish":
      return { ...state, airplaneUpdating: false };
    case "model-start":
      return {
        ...state,
        selectedLocalModel: action.model,
        modelUpdateError: null,
        modelUpdating: true,
      };
    case "model-success":
      return { ...state, modelUpdating: false };
    case "model-error":
      return {
        ...state,
        selectedLocalModel: action.previousModel,
        modelUpdateError: action.error,
        modelUpdating: false,
      };
    case "test-start":
      return { ...state, testingLocalBackend: true, testConnectionResult: null };
    case "test-result":
      return { ...state, testConnectionResult: action.result };
    case "test-finish":
      return { ...state, testingLocalBackend: false };
    default:
      return state;
  }
}

function canonicalLocalBackendIntegration(agentId: string): {
  displayId: string;
  integrationId: string;
} {
  if (agentId === "copilot" || agentId === "copilot-cli") {
    return { displayId: "copilot-cli", integrationId: "copilot" };
  }
  return { displayId: agentId, integrationId: agentId };
}

function getNotReadyReason(ollamaResult: LocalBackendStatus["ollama"]): string {
  if (!ollamaResult?.installed) {
    return "Ollama binary is not detected.";
  }
  if (!ollamaResult.server_running) {
    return "Ollama is installed but the server is not running.";
  }
  if (!ollamaResult.models || ollamaResult.models.length === 0) {
    return "Ollama is running but has no local models.";
  }
  if (ollamaResult.has_configured_model === false) {
    return "The configured model is not installed locally.";
  }
  return "Local backend is not ready.";
}

function useLocalBackendController() {
  const {
    airplaneMode,
    airplaneModeReady,
    airplaneModeError,
    toggleAirplaneMode,
  } = useAirplaneModeStore();
  const [state, dispatch] = useReducer(
    localBackendReducer,
    INITIAL_LOCAL_BACKEND_STATE,
  );
  const {
    data: localBackendStatus,
    loading: localBackendLoading,
    error: localBackendError,
    refetch: refetchLocalBackendStatus,
  } = useMcpQuery<LocalBackendStatus>(
    "airplane-status",
    "get-local-backend-status",
    "static",
    { refetchInterval: 5000 },
  );
  const {
    data: ollamaIntegrations,
    loading: ollamaIntegrationsLoading,
    error: ollamaIntegrationsError,
  } = useMcpQuery<OllamaIntegrations>(
    "ollama-integrations",
    "list-ollama-integrations",
    "static",
    { refetchInterval: 60000 },
  );

  const configuredLocalModel = localBackendStatus?.ollama?.configured_model ?? "";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      dispatch({ type: "sync-selected-model", model: configuredLocalModel });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [configuredLocalModel]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      dispatch({ type: "set-mounted" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleToggleAirplaneMode = useCallback(async () => {
    if (!airplaneModeReady || state.airplaneUpdating) return;
    dispatch({ type: "airplane-start" });
    try {
      await toggleAirplaneMode();
    } catch (err) {
      dispatch({
        type: "airplane-error",
        error:
          err instanceof Error
            ? err.message
            : "Failed to update airplane mode. Check preferences.yaml permissions.",
      });
    } finally {
      dispatch({ type: "airplane-finish" });
    }
  }, [airplaneModeReady, state.airplaneUpdating, toggleAirplaneMode]);

  const handleLocalModelChange = useCallback(
    async (model: string) => {
      dispatch({ type: "model-start", model });
      try {
        const result = await mcpCall<PreferenceWriteResult>("update-preference", {
          key: "local_backends.ollama.model",
          value: model,
        });
        if (result?.success === false) {
          throw new Error(
            result.error ||
              result.details ||
              result.message ||
              "Failed to update local model preference.",
          );
        }
        refetchLocalBackendStatus();
        dispatch({ type: "model-success" });
      } catch (err) {
        dispatch({
          type: "model-error",
          previousModel: configuredLocalModel,
          error:
            err instanceof Error
              ? err.message
              : "Failed to update local model preference.",
        });
      }
    },
    [configuredLocalModel, refetchLocalBackendStatus],
  );

  const handleTestLocalBackendConnection = useCallback(async () => {
    dispatch({ type: "test-start" });
    try {
      const result = await mcpCall<LocalBackendStatus>("get-local-backend-status", {});
      const ollamaResult = result?.ollama;
      const configuredModelPresent = ollamaResult?.has_configured_model === true;
      const connectionResult: TestConnectionResult =
        ollamaResult?.ready === true && configuredModelPresent
          ? {
              status: "ready",
              message: `Ready${ollamaResult.configured_model ? `: ${ollamaResult.configured_model}` : ""}`,
            }
          : {
              status: "not-ready",
              message: `Not ready: ${getNotReadyReason(ollamaResult)}`,
            };
      dispatch({ type: "test-result", result: connectionResult });
      refetchLocalBackendStatus();
    } catch (err) {
      dispatch({
        type: "test-result",
        result: {
          status: "error",
          message:
            err instanceof Error
              ? err.message
              : "Could not test the local backend connection.",
        },
      });
    } finally {
      dispatch({ type: "test-finish" });
    }
  }, [refetchLocalBackendStatus]);

  const airplaneDisplayError =
    state.airplaneToggleError ??
    (airplaneModeError
      ? `Could not read airplane mode from preferences.yaml: ${airplaneModeError}`
      : null);
  const airplaneStateLabel = !airplaneModeReady
    ? "Loading"
    : airplaneMode
      ? "ON"
      : "OFF";
  const airplaneDescription = !airplaneModeReady
    ? "Reading airplane mode from preferences.yaml."
    : airplaneMode
      ? "CLI sessions run without auto-approve flags."
      : "CLI sessions may include auto-approve flags when configured.";
  const airplaneButtonLabel = !airplaneModeReady
    ? "Loading"
    : state.airplaneUpdating
      ? "Updating"
      : airplaneMode
        ? "Turn OFF"
        : "Turn ON";

  const localBackendStatusReady =
    state.localBackendMounted && !localBackendLoading && !localBackendError;
  const integrationsReady =
    state.localBackendMounted &&
    !ollamaIntegrationsLoading &&
    !ollamaIntegrationsError;
  const ollama = localBackendStatusReady ? localBackendStatus?.ollama : undefined;
  const ollamaConnectionReady =
    ollama?.ready === true && ollama?.has_configured_model === true;
  const localModels = Array.isArray(ollama?.models) ? ollama.models : [];
  const installedModelOptions: string[] = [];
  for (const model of localModels) {
    if (model.name) {
      installedModelOptions.push(model.name);
    }
  }
  const modelOptions =
    configuredLocalModel &&
    !installedModelOptions.includes(configuredLocalModel)
      ? [configuredLocalModel, ...installedModelOptions]
      : installedModelOptions;
  const supportedIntegrationMap = new Map<
    string,
    ReturnType<typeof canonicalLocalBackendIntegration>
  >();
  for (const integration of ollamaIntegrations?.integrations ?? []) {
    if (typeof integration !== "string") continue;
    const trimmed = integration.trim();
    if (!trimmed) continue;
    const canonical = canonicalLocalBackendIntegration(trimmed);
    if (UNSUPPORTED_LOCAL_BACKEND_AGENT_SET.has(canonical.displayId)) continue;
    supportedIntegrationMap.set(canonical.displayId, canonical);
  }

  return {
    airplaneButtonLabel,
    airplaneDescription,
    airplaneDisplayError,
    airplaneMode,
    airplaneModeReady,
    airplaneStateLabel,
    airplaneUpdating: state.airplaneUpdating,
    configuredLocalModel,
    handleLocalModelChange,
    handleTestLocalBackendConnection,
    handleToggleAirplaneMode,
    integrationsReady,
    localBackendError,
    localBackendLoading,
    localBackendMounted: state.localBackendMounted,
    modelOptions,
    modelUpdateError: state.modelUpdateError,
    modelUpdating: state.modelUpdating,
    ollama,
    ollamaConnectionReady,
    ollamaIntegrationsError,
    ollamaIntegrationsLoading,
    selectedLocalModel: state.selectedLocalModel,
    supportedIntegrations: Array.from(supportedIntegrationMap.values()),
    testConnectionResult: state.testConnectionResult,
    testingLocalBackend: state.testingLocalBackend,
  };
}

type LocalBackendController = ReturnType<typeof useLocalBackendController>;

/**
 * Local Ollama backend + airplane mode controls. Extracted from the old
 * Security tab into the AI & Models tab, where it sits alongside the System
 * LLM "local" profile it backs (ADR: settings IA cleanup).
 */
export default function LocalBackendSection() {
  const controller = useLocalBackendController();

  return (
    <section>
      <LocalBackendHeading />
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 space-y-5">
        <LocalBackendStatusGrid controller={controller} />
        <AirplaneModeControl controller={controller} />
        {controller.airplaneDisplayError && (
          <AlertMessage>{controller.airplaneDisplayError}</AlertMessage>
        )}
        <AgentCompatibilityList controller={controller} />
      </div>
    </section>
  );
}

function LocalBackendHeading() {
  return (
    <div className="flex items-center gap-3 mb-4">
      <Cpu className="size-5 text-[var(--accent-warning)]" />
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Local Backend
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Route compatible agents through local Ollama execution
          </p>
        </div>
      </div>
    </div>
  );
}

function LocalBackendStatusGrid({
  controller,
}: {
  controller: LocalBackendController;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <OllamaBinaryCard controller={controller} />
      <LocalModelCard controller={controller} />
      <ConnectionCard controller={controller} />
    </div>
  );
}

function OllamaBinaryCard({ controller }: { controller: LocalBackendController }) {
  const { localBackendMounted, localBackendLoading, localBackendError, ollama } =
    controller;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Ollama binary
      </p>
      {!localBackendMounted || localBackendLoading ? (
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Checking local backend…
        </p>
      ) : localBackendError ? (
        <p className="mt-2 text-sm text-[var(--accent-danger)]">
          Could not read local backend status.
        </p>
      ) : ollama?.binary ? (
        <code className="mt-2 block break-all rounded border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-1.5 text-xs text-[var(--text-primary)]">
          {ollama.binary}
        </code>
      ) : (
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Ollama binary not detected.
        </p>
      )}
      {ollama?.version && (
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Version {ollama.version}
        </p>
      )}
    </div>
  );
}

function LocalModelCard({ controller }: { controller: LocalBackendController }) {
  const {
    configuredLocalModel,
    handleLocalModelChange,
    modelOptions,
    modelUpdateError,
    modelUpdating,
    ollama,
    selectedLocalModel,
  } = controller;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <label
        htmlFor="ai-local-model"
        className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]"
      >
        Local model
      </label>
      <select
        id="ai-local-model"
        value={selectedLocalModel || configuredLocalModel}
        onChange={(event) => {
          void handleLocalModelChange(event.target.value);
        }}
        disabled={modelUpdating || modelOptions.length === 0}
        className="mt-2 h-10 w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {modelOptions.length > 0 ? (
          modelOptions.map((model) => (
            <option key={model} value={model}>
              {model}
              {model === configuredLocalModel &&
              ollama?.has_configured_model === false
                ? " (configured, missing)"
                : ""}
            </option>
          ))
        ) : (
          <option value="">No local models detected</option>
        )}
      </select>
      <p className="mt-2 text-xs text-[var(--text-muted)]">
        {modelUpdating
          ? "Saving model preference..."
          : ollama?.has_configured_model === false
            ? "Configured model is not installed locally."
            : "Used for compatible local agent launches."}
      </p>
      {modelUpdateError && <AlertMessage>{modelUpdateError}</AlertMessage>}
    </div>
  );
}

function ConnectionCard({ controller }: { controller: LocalBackendController }) {
  const {
    handleTestLocalBackendConnection,
    ollama,
    ollamaConnectionReady,
    testConnectionResult,
    testingLocalBackend,
  } = controller;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Connection
      </p>
      <p className="mt-2 text-sm text-[var(--text-primary)]">
        {ollamaConnectionReady ? "Ollama ready" : "Ollama setup required"}
      </p>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        Server {ollama?.server_running ? "running" : "not running"}.
      </p>
      <Button
        variant="outline"
        onClick={() => {
          void handleTestLocalBackendConnection();
        }}
        disabled={testingLocalBackend}
        className="mt-3 w-full gap-2"
      >
        {testingLocalBackend ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <RefreshCw className="size-4" />
        )}
        Test connection
      </Button>
      {testConnectionResult && (
        <div
          role={testConnectionResult.status === "error" ? "alert" : "status"}
          className={`mt-3 rounded-lg border px-3 py-2 text-xs ${CONNECTION_RESULT_STYLES[testConnectionResult.status]}`}
        >
          {testConnectionResult.message}
        </div>
      )}
    </div>
  );
}

function AirplaneModeControl({
  controller,
}: {
  controller: LocalBackendController;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-medium text-[var(--text-primary)]">
          Airplane mode: {controller.airplaneStateLabel}
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          {controller.airplaneDescription}
        </p>
      </div>
      <Button
        variant={
          controller.airplaneModeReady && controller.airplaneMode
            ? "outline"
            : "default"
        }
        onClick={() => {
          void controller.handleToggleAirplaneMode();
        }}
        disabled={!controller.airplaneModeReady || controller.airplaneUpdating}
        className="gap-2 shrink-0"
      >
        {!controller.airplaneModeReady || controller.airplaneUpdating ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Plane className="size-4" />
        )}
        {controller.airplaneButtonLabel}
      </Button>
    </div>
  );
}

function AlertMessage({ children }: { children: string }) {
  return (
    <div
      role="alert"
      className="mt-2 flex items-start gap-2 rounded-lg border border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--accent-danger)]"
    >
      <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

function AgentCompatibilityList({
  controller,
}: {
  controller: LocalBackendController;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <div className="border-b border-[var(--border-color)] px-4 py-3">
        <p className="text-sm font-medium text-[var(--text-primary)]">
          Agent compatibility
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Supported rows come from Ollama; unsupported rows are fixed for this
          release.
        </p>
      </div>
      <div className="divide-y divide-[var(--border-color)]">
        {(!controller.localBackendMounted ||
          controller.ollamaIntegrationsLoading) && (
          <div className="flex items-center gap-2 px-4 py-3 text-sm text-[var(--text-secondary)]">
            <Loader2 className="size-4 animate-spin" />
            Loading integrations…
          </div>
        )}
        {controller.ollamaIntegrationsError && (
          <div className="flex items-start gap-2 px-4 py-3 text-sm text-[var(--accent-warning)]">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            <span>Could not read Ollama integration support.</span>
          </div>
        )}
        {controller.integrationsReady &&
          controller.supportedIntegrations.length === 0 && (
            <div className="px-4 py-3 text-sm text-[var(--text-secondary)]">
              No supported Ollama integrations detected.
            </div>
          )}
        {controller.supportedIntegrations.map(({ displayId, integrationId }) => (
          <IntegrationRow
            key={displayId}
            integration={displayId}
            status="Supported"
            detail={displayId === integrationId ? "" : `via ${integrationId}`}
            tone="success"
          />
        ))}
        {UNSUPPORTED_LOCAL_BACKEND_AGENTS.map((integration) => (
          <IntegrationRow
            key={integration}
            integration={integration}
            status="Not supported"
            detail="Ollama launch does not support this agent yet."
            tone="danger"
          />
        ))}
      </div>
    </div>
  );
}

function IntegrationRow({
  integration,
  status,
  detail,
  tone,
}: {
  integration: string;
  status: string;
  detail: string;
  tone: "success" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 text-[var(--accent-success)]"
      : "border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)]";

  return (
    <div className="grid gap-2 px-4 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_8rem_minmax(0,2fr)] sm:items-center">
      <span className="font-medium text-[var(--text-primary)]">
        {integration}
      </span>
      <span className={`w-max rounded-full border px-2 py-0.5 text-xs font-medium ${toneClass}`}>
        {status}
      </span>
      <span className="text-xs text-[var(--text-muted)]">{detail}</span>
    </div>
  );
}
