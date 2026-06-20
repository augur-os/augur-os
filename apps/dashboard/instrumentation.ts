export async function register() {
  // MCP requests already establish the bridge lazily on demand.
  // Keep the instrumentation hook inert so dashboard startup does not depend
  // on prewarming server-only bridge code during Next.js initialization.
}
