import type { HelpPayload, StrippedItem } from "@/lib/help/stripPII";

export interface HelpRequestModalProps {
  onClose: () => void;
}

export type HelpTopic = "bug" | "howto" | "feature" | "performance" | "general";

export type HelpTopicOption = {
  value: HelpTopic;
  label: string;
  description: string;
};

export interface HelpRequestState {
  step: number;
  topic: HelpTopic | null;
  description: string;
  includeBrowserErrors: boolean;
  emailNotify: boolean;
  userEmail: string;
  consentGiven: boolean;
  browserErrors: string[];
  submitted: boolean;
  submitError: string | null;
  ticketId: string | null;
}

export type HelpRequestAction =
  | { type: "set-step"; step: number }
  | { type: "set-topic"; topic: HelpTopic }
  | { type: "set-description"; description: string }
  | { type: "set-include-browser-errors"; includeBrowserErrors: boolean }
  | { type: "set-email-notify"; emailNotify: boolean }
  | { type: "set-user-email"; userEmail: string }
  | { type: "set-consent"; consentGiven: boolean }
  | { type: "set-browser-errors"; browserErrors: string[] }
  | { type: "append-browser-error"; message: string }
  | { type: "submit-start" }
  | { type: "submit-success"; ticketId: string | null }
  | { type: "submit-error"; submitError: string };

export type { HelpPayload, StrippedItem };
