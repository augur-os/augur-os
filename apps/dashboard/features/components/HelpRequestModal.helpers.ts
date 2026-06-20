import { stripPayloadPII, type HelpPayload } from "@/lib/help/stripPII";
import { getSupportToken } from "@/lib/help/supportToken";
import type {
  HelpRequestState,
  HelpRequestAction,
  HelpTopic,
  HelpTopicOption,
} from "./HelpRequestModal.types";

export const TOPICS: HelpTopicOption[] = [
  {
    value: "bug",
    label: "Something is broken",
    description: "An error, crash, or unexpected behavior",
  },
  {
    value: "howto",
    label: "I need guidance",
    description: "I don't know how to do something",
  },
  {
    value: "feature",
    label: "Feature request",
    description: "I want something new or different",
  },
  {
    value: "performance",
    label: "Performance issue",
    description: "Something is slow or doesn't respond",
  },
  {
    value: "general",
    label: "Other",
    description: "General question or feedback",
  },
];

export const STEP_LABELS = ["Topic", "Details", "Logs", "Review"];
export const TOTAL_STEPS = 4;

export function detectSkill(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }

  const segments = pathname.split("/").filter(Boolean);
  return segments.length > 0 ? segments[0] : null;
}

export function collectCurrentBrowserErrors(): string[] {
  const errors: string[] = [];

  const errorElements = document.querySelectorAll("[data-nextjs-error]");
  errorElements.forEach((element) => {
    const text = element.textContent?.trim();
    if (text) {
      errors.push(text.slice(0, 500));
    }
  });

  const reactOverlay = document.querySelector("[data-nextjs-dialog]");
  if (reactOverlay) {
    const text = reactOverlay.textContent?.trim();
    if (text) {
      errors.push(text.slice(0, 500));
    }
  }

  return errors;
}

export function getModeLabel(): "dev" | "operation" {
  if (
    typeof localStorage !== "undefined" &&
    localStorage.getItem("augur_dev_mode") === "true"
  ) {
    return "dev";
  }

  return "operation";
}

export function getBrowserLabel(): string {
  if (typeof navigator === "undefined") {
    return "Unknown";
  }

  return navigator.userAgent.match(/Chrome\/[\d.]+/)?.[0] || "Unknown";
}

export function buildPreviewPayload({
  topic,
  description,
  pathname,
  skill,
  includeBrowserErrors,
  browserErrors,
  emailNotify,
  userEmail,
}: {
  topic: HelpTopic;
  description: string;
  pathname: string | null;
  skill: string | null;
  includeBrowserErrors: boolean;
  browserErrors: string[];
  emailNotify: boolean;
  userEmail: string;
}) {
  const payload: HelpPayload = {
    topic,
    description,
    context: {
      page: pathname || "/",
      skill,
      mode: getModeLabel(),
      browser: getBrowserLabel(),
    },
    supportToken: getSupportToken(),
    timestamp: new Date().toISOString(),
  };

  if (includeBrowserErrors && browserErrors.length > 0) {
    payload.logs = { browserErrors };
  }

  if (emailNotify && userEmail) {
    payload.email_notification = userEmail;
  }

  return stripPayloadPII(payload);
}

export function canProceed(
  step: number,
  topic: HelpTopic | null,
  description: string,
  consentGiven: boolean,
) {
  switch (step) {
    case 1:
      return topic !== null;
    case 2:
      return description.trim().length > 10;
    case 3:
      return true;
    case 4:
      return consentGiven;
    default:
      return false;
  }
}

export const INITIAL_HELP_REQUEST_STATE: HelpRequestState = {
  step: 1,
  topic: null,
  description: "",
  includeBrowserErrors: false,
  emailNotify: false,
  userEmail: "",
  consentGiven: false,
  browserErrors: [],
  submitted: false,
  submitError: null,
  ticketId: null,
};

export function helpRequestReducer(
  state: HelpRequestState,
  action: HelpRequestAction,
): HelpRequestState {
  switch (action.type) {
    case "set-step":
      return { ...state, step: action.step };
    case "set-topic":
      return { ...state, topic: action.topic };
    case "set-description":
      return { ...state, description: action.description };
    case "set-include-browser-errors":
      return {
        ...state,
        includeBrowserErrors: action.includeBrowserErrors,
      };
    case "set-email-notify":
      return {
        ...state,
        emailNotify: action.emailNotify,
        userEmail: action.emailNotify ? state.userEmail : "",
      };
    case "set-user-email":
      return { ...state, userEmail: action.userEmail };
    case "set-consent":
      return { ...state, consentGiven: action.consentGiven };
    case "set-browser-errors":
      return { ...state, browserErrors: action.browserErrors };
    case "append-browser-error":
      return {
        ...state,
        browserErrors: [...state.browserErrors, action.message.slice(0, 500)],
      };
    case "submit-start":
      return { ...state, submitError: null };
    case "submit-success":
      return { ...state, submitted: true, ticketId: action.ticketId };
    case "submit-error":
      return { ...state, submitError: action.submitError };
    default:
      return state;
  }
}
