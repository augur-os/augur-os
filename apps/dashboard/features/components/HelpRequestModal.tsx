"use client";

import { useReducer, useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { X, HelpCircle } from "lucide-react";
import { type HelpPayload, type StrippedItem } from "@/lib/help/stripPII";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
import type { HelpRequestModalProps } from "./HelpRequestModal.types";
import {
  detectSkill,
  collectCurrentBrowserErrors,
  buildPreviewPayload,
  canProceed,
  helpRequestReducer,
  INITIAL_HELP_REQUEST_STATE,
} from "./HelpRequestModal.helpers";
import {
  SuccessState,
  StepIndicator,
  StepContent,
  FooterActions,
} from "./HelpRequestModal.steps";

export default function HelpRequestModal({ onClose }: HelpRequestModalProps) {
  const pathname = usePathname();
  const [state, dispatch] = useReducer(
    helpRequestReducer,
    INITIAL_HELP_REQUEST_STATE,
  );
  const {
    step,
    topic,
    description,
    includeBrowserErrors,
    emailNotify,
    userEmail,
    consentGiven,
    browserErrors,
    submitted,
    submitError,
    ticketId,
  } = state;
  const skill = useMemo(() => detectSkill(pathname), [pathname]);

  const { cleaned: previewPayload, strippedItems } = useMemo(() => {
    if (step !== 4 || !topic) {
      return {
        cleaned: null as HelpPayload | null,
        strippedItems: [] as StrippedItem[],
      };
    }

    return buildPreviewPayload({
      topic,
      description,
      pathname,
      skill,
      includeBrowserErrors,
      browserErrors,
      emailNotify,
      userEmail,
    });
  }, [
    step,
    topic,
    description,
    pathname,
    skill,
    includeBrowserErrors,
    browserErrors,
    emailNotify,
    userEmail,
  ]);

  const { mutate: submitHelpRequest, loading: submitting } =
    useMcpMutation<unknown, HelpPayload>("file-write", {
      staticArgs: { scope: "help-request" },
    });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const timer = window.setTimeout(() => {
      dispatch({
        type: "set-browser-errors",
        browserErrors: collectCurrentBrowserErrors(),
      });
    }, 0);

    const errorHandler = (event: ErrorEvent) => {
      const message = `${event.message} at ${event.filename}:${event.lineno}`;
      dispatch({ type: "append-browser-error", message });
    };

    window.addEventListener("error", errorHandler);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("error", errorHandler);
    };
  }, []);

  const handleSubmit = async () => {
    if (!previewPayload || !consentGiven) {
      return;
    }

    dispatch({ type: "submit-start" });

    try {
      const data = (await submitHelpRequest(previewPayload)) as unknown as {
        success?: boolean;
        ticketId?: string;
        error?: string;
      };
      if (data.success) {
        dispatch({ type: "submit-success", ticketId: data.ticketId ?? null });
      } else {
        dispatch({
          type: "submit-error",
          submitError: data.error || "Failed to submit help request",
        });
      }
    } catch {
      dispatch({
        type: "submit-error",
        submitError: "Network error. Your request has been saved locally.",
      });
    }
  };

  if (submitted) {
    return <SuccessState ticketId={ticketId} onClose={onClose} />;
  }

  const readyForNextStep = canProceed(step, topic, description, consentGiven);

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-2xl max-h-[90vh] flex flex-col rounded-lg border border-[var(--border-color)] shadow-2xl">
        <div className="flex items-center justify-between p-6 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <HelpCircle className="size-5 text-[var(--accent-primary)]" />
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">
              Get Help
            </h2>
          </div>
          <button type="button"
            onClick={onClose}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-2 hover:bg-[var(--bg-hover)] rounded-lg"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        <StepIndicator step={step} />

        <div className="flex-1 overflow-y-auto p-6">
          <StepContent
            step={step}
            topic={topic}
            setTopic={(nextTopic) =>
              dispatch({ type: "set-topic", topic: nextTopic })
            }
            pathname={pathname}
            skill={skill}
            description={description}
            setDescription={(nextDescription) =>
              dispatch({
                type: "set-description",
                description: nextDescription,
              })
            }
            includeBrowserErrors={includeBrowserErrors}
            setIncludeBrowserErrors={(nextIncludeBrowserErrors) =>
              dispatch({
                type: "set-include-browser-errors",
                includeBrowserErrors: nextIncludeBrowserErrors,
              })
            }
            browserErrors={browserErrors}
            emailNotify={emailNotify}
            setEmailNotify={(nextEmailNotify) =>
              dispatch({
                type: "set-email-notify",
                emailNotify: nextEmailNotify,
              })
            }
            userEmail={userEmail}
            setUserEmail={(nextUserEmail) =>
              dispatch({ type: "set-user-email", userEmail: nextUserEmail })
            }
            strippedItems={strippedItems}
            previewPayload={previewPayload}
            consentGiven={consentGiven}
            setConsentGiven={(nextConsentGiven) =>
              dispatch({ type: "set-consent", consentGiven: nextConsentGiven })
            }
            submitError={submitError}
          />
        </div>

        <FooterActions
          step={step}
          canGoNext={readyForNextStep}
          onBack={() => dispatch({ type: "set-step", step: step - 1 })}
          onCancel={onClose}
          onNext={() => dispatch({ type: "set-step", step: step + 1 })}
          onSubmit={handleSubmit}
          submitting={submitting}
        />
      </div>
    </div>
  );
}
