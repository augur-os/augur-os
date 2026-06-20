import { type deriveControlState } from './control-state';

export type ClientRoutingPreferencesResponse = {
  client_routing?: {
    default_client?: string;
  };
};

export type UpdatePreferenceResult = {
  success?: boolean;
  error?: string;
  details?: string;
  message?: string;
};

export type AgentControlState = ReturnType<typeof deriveControlState>;

export type RegistryCoverage = {
  mcpCapable: number;
  isolated: number;
  roles: string[];
};

export type ConfigureAgentModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
};

export interface ConfigureAgentState {
  agentId: string;
  command: string;
  model: string;
  isSaving: boolean;
  saveError: string | null;
}

export type ConfigureAgentAction =
  | { type: 'set-field'; field: 'agentId' | 'command' | 'model'; value: string }
  | { type: 'save-start' }
  | { type: 'save-error'; error: string }
  | { type: 'reset' };
