import type { AgentBubbleState, BlockState, FormState, NavigationState, PageState, ViewState } from "./types";

type SettleWaiter = {
  blockId: string;
  resolve: (state: BlockState) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

type ConfigListener = (config: Record<string, unknown>) => void;
type RefreshListener = () => void;
type FormFillListener = (fields: Record<string, unknown>) => void;
type FormSubmitListener = () => void;

/**
 * In-memory state map for WebMCP. Stores block state reported by components.
 * Also provides event channels so tool execute callbacks (blocks.configure,
 * blocks.act) can push config changes and refresh signals to React components.
 */
export class StateRegistry {
  private blocks = new Map<string, BlockState>();
  private pages = new Map<string, PageState>();
  private views = new Map<string, ViewState>();
  private forms = new Map<string, FormState>();
  private agents = new Map<string, AgentBubbleState>();
  private navigation: NavigationState | null = null;
  private settleWaiters: SettleWaiter[] = [];
  private configListeners = new Map<string, Set<ConfigListener>>();
  private refreshListeners = new Map<string, Set<RefreshListener>>();
  private formFillListeners = new Map<string, Set<FormFillListener>>();
  private formSubmitListeners = new Map<string, Set<FormSubmitListener>>();

  reportBlock(state: BlockState): void {
    this.blocks.set(state.blockId, { ...state, lastUpdated: Date.now() });
    this.checkSettleWaiters(state);
  }

  removeBlock(blockId: string, _instanceId: string): void {
    this.blocks.delete(blockId);
    this.configListeners.delete(blockId);
    this.refreshListeners.delete(blockId);
  }

  getBlock(blockId: string): BlockState | undefined {
    return this.blocks.get(blockId);
  }

  getAllBlocks(): BlockState[] {
    return Array.from(this.blocks.values());
  }

  filterBlocks(predicate: (b: BlockState) => boolean): BlockState[] {
    return this.getAllBlocks().filter(predicate);
  }

  waitForSettle(blockId: string, timeoutMs: number): Promise<BlockState> {
    const current = this.blocks.get(blockId);
    if (current && (current.renderState === "ready" || current.renderState === "error")) {
      return Promise.resolve(current);
    }

    return new Promise<BlockState>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.settleWaiters = this.settleWaiters.filter((w) => w.blockId !== blockId);
        reject(new Error(`waitForSettle("${blockId}") timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this.settleWaiters.push({ blockId, resolve, reject, timer });
    });
  }

  private checkSettleWaiters(state: BlockState): void {
    if (state.renderState !== "ready" && state.renderState !== "error") return;

    const matching = this.settleWaiters.filter((w) => w.blockId === state.blockId);
    this.settleWaiters = this.settleWaiters.filter((w) => w.blockId !== state.blockId);

    for (const waiter of matching) {
      clearTimeout(waiter.timer);
      waiter.resolve(state);
    }
  }

  // --- Config change events (used by blocks.configure) ---

  onConfigChange(blockId: string, listener: ConfigListener): () => void {
    if (!this.configListeners.has(blockId)) {
      this.configListeners.set(blockId, new Set());
    }
    this.configListeners.get(blockId)!.add(listener);
    return () => { this.configListeners.get(blockId)?.delete(listener); };
  }

  setConfig(blockId: string, config: Record<string, unknown>): void {
    const listeners = this.configListeners.get(blockId);
    if (listeners) {
      for (const fn of listeners) fn(config);
    }
  }

  // --- Refresh events (used by blocks.act "refresh") ---

  onRefresh(blockId: string, listener: RefreshListener): () => void {
    if (!this.refreshListeners.has(blockId)) {
      this.refreshListeners.set(blockId, new Set());
    }
    this.refreshListeners.get(blockId)!.add(listener);
    return () => { this.refreshListeners.get(blockId)?.delete(listener); };
  }

  triggerRefresh(blockId: string): void {
    const listeners = this.refreshListeners.get(blockId);
    if (listeners) {
      for (const fn of listeners) fn();
    }
  }

  // --- Page state ---

  reportPage(state: PageState): void {
    this.pages.set(state.pageId, { ...state, lastUpdated: Date.now() });
  }

  removePage(pageId: string): void {
    this.pages.delete(pageId);
  }

  getPage(pageId: string): PageState | undefined {
    return this.pages.get(pageId);
  }

  getAllPages(): PageState[] {
    return Array.from(this.pages.values());
  }

  // --- View state ---

  reportView(state: ViewState): void {
    this.views.set(state.viewId, { ...state, lastUpdated: Date.now() });
  }

  removeView(viewId: string): void {
    this.views.delete(viewId);
  }

  getView(viewId: string): ViewState | undefined {
    return this.views.get(viewId);
  }

  getAllViews(): ViewState[] {
    return Array.from(this.views.values());
  }

  // --- Form state ---

  reportForm(state: FormState): void {
    this.forms.set(state.formId, { ...state, lastUpdated: Date.now() });
  }

  removeForm(formId: string): void {
    this.forms.delete(formId);
    this.formFillListeners.delete(formId);
    this.formSubmitListeners.delete(formId);
  }

  getForm(formId: string): FormState | undefined {
    return this.forms.get(formId);
  }

  getAllForms(): FormState[] {
    return Array.from(this.forms.values());
  }

  // Event channels for forms.fill and forms.submit

  onFormFill(formId: string, listener: FormFillListener): () => void {
    if (!this.formFillListeners.has(formId)) {
      this.formFillListeners.set(formId, new Set());
    }
    this.formFillListeners.get(formId)!.add(listener);
    return () => { this.formFillListeners.get(formId)?.delete(listener); };
  }

  triggerFormFill(formId: string, fields: Record<string, unknown>): void {
    const listeners = this.formFillListeners.get(formId);
    if (listeners) {
      for (const fn of listeners) fn(fields);
    }
  }

  onFormSubmit(formId: string, listener: FormSubmitListener): () => void {
    if (!this.formSubmitListeners.has(formId)) {
      this.formSubmitListeners.set(formId, new Set());
    }
    this.formSubmitListeners.get(formId)!.add(listener);
    return () => { this.formSubmitListeners.get(formId)?.delete(listener); };
  }

  triggerFormSubmit(formId: string): void {
    const listeners = this.formSubmitListeners.get(formId);
    if (listeners) {
      for (const fn of listeners) fn();
    }
  }

  // --- Agent state ---

  reportAgent(state: AgentBubbleState): void {
    this.agents.set(state.bubbleId, { ...state, lastUpdated: Date.now() });
  }

  removeAgent(bubbleId: string): void {
    this.agents.delete(bubbleId);
  }

  getAgent(bubbleId: string): AgentBubbleState | undefined {
    return this.agents.get(bubbleId);
  }

  getAllAgents(): AgentBubbleState[] {
    return Array.from(this.agents.values());
  }

  // --- Navigation state ---

  reportNavigation(state: NavigationState): void {
    this.navigation = { ...state };
  }

  getNavigation(): NavigationState | null {
    return this.navigation;
  }

  clear(): void {
    this.blocks.clear();
    this.pages.clear();
    this.views.clear();
    this.forms.clear();
    this.agents.clear();
    this.navigation = null;
    this.configListeners.clear();
    this.refreshListeners.clear();
    this.formFillListeners.clear();
    this.formSubmitListeners.clear();
    for (const w of this.settleWaiters) {
      clearTimeout(w.timer);
      w.reject(new Error("Registry cleared"));
    }
    this.settleWaiters = [];
  }
}
