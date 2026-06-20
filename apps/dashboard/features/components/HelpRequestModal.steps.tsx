"use client";

import {
  ChevronRight,
  ChevronLeft,
  Send,
  Loader2,
  AlertTriangle,
  Check,
  Eye,
  Mail,
} from "lucide-react";
import type { HelpPayload, StrippedItem } from "@/lib/help/stripPII";
import { TOPICS, STEP_LABELS, TOTAL_STEPS } from "./HelpRequestModal.helpers";
import type { HelpTopic } from "./HelpRequestModal.types";

export function SuccessState({
  ticketId,
  onClose,
}: {
  ticketId: string | null;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-lg rounded-lg border border-[var(--border-color)] shadow-2xl p-8 text-center">
        <div className="size-12 rounded-full bg-[var(--accent-success)]/15 flex items-center justify-center mx-auto mb-4">
          <Check className="size-6 text-[var(--accent-success)]" />
        </div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Request Submitted
        </h2>
        {ticketId && (
          <p className="text-sm text-[var(--text-muted)] mb-4 font-mono">
            {ticketId}
          </p>
        )}
        <p className="text-sm text-[var(--text-secondary)] mb-6">
          {"You'll receive a notification when a resolution is available."}
        </p>
        <button type="button"
          onClick={onClose}
          className="px-6 py-2 bg-[var(--accent-primary)] hover:opacity-90 rounded-lg text-sm font-medium text-white transition-all"
        >
          Close
        </button>
      </div>
    </div>
  );
}

export function StepIndicator({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-2 px-6 pt-4">
      {Array.from({ length: TOTAL_STEPS }, (_, index) => {
        const stepNumber = index + 1;
        const isCurrent = stepNumber === step;
        const isComplete = stepNumber < step;

        return (
          <div key={stepNumber} className="flex items-center gap-2 flex-1">
            <div
              className={`flex items-center gap-1.5 ${
                isCurrent
                  ? "text-[var(--accent-primary)]"
                  : isComplete
                    ? "text-[var(--accent-success)]"
                    : "text-[var(--text-muted)]"
              }`}
            >
              <div
                className={`size-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  isCurrent
                    ? "bg-[var(--accent-primary)]/15 border border-[var(--accent-primary)]/30"
                    : isComplete
                      ? "bg-[var(--accent-success)]/15 border border-[var(--accent-success)]/30"
                      : "bg-[var(--bg-secondary)] border border-[var(--border-color)]"
                }`}
              >
                {isComplete ? <Check className="size-3" /> : stepNumber}
              </div>
              <span className="text-xs font-medium hidden sm:inline">
                {STEP_LABELS[index]}
              </span>
            </div>
            {stepNumber < TOTAL_STEPS && (
              <div
                className={`flex-1 h-px ${
                  isComplete ? "bg-[var(--accent-success)]/30" : "bg-[var(--border-color)]"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function StepTopic({
  topic,
  onTopicChange,
}: {
  topic: HelpTopic | null;
  onTopicChange: (nextTopic: HelpTopic) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--text-secondary)] mb-4">
        What do you need help with?
      </p>
      {TOPICS.map((item) => {
        const isSelected = topic === item.value;

        return (
          <button type="button"
            key={item.value}
            onClick={() => onTopicChange(item.value)}
            className={`w-full text-left p-4 rounded-lg border transition-colors ${
              isSelected
                ? "border-[var(--accent-primary)]/50 bg-[var(--accent-primary)]/5"
                : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-[var(--text-muted)]"
            }`}
          >
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {item.label}
            </div>
            <div className="text-xs text-[var(--text-muted)] mt-1">
              {item.description}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function StepDetails({
  pathname,
  skill,
  description,
  onDescriptionChange,
}: {
  pathname: string | null;
  skill: string | null;
  description: string;
  onDescriptionChange: (value: string) => void;
}) {
  const minLengthStatus =
    description.length < 10
      ? `At least 10 characters required (${description.length}/10)`
      : `${description.length} characters`;

  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-secondary)] rounded-lg p-4 border border-[var(--border-color)]">
        <div className="text-xs uppercase text-[var(--text-muted)] mb-2">
          Detected Context
        </div>
        <div className="space-y-1 text-sm">
          <div>
            <span className="text-[var(--text-secondary)]">Page:</span>{" "}
            <span className="text-[var(--text-primary)] font-mono text-xs">
              {pathname}
            </span>
          </div>
          {skill && (
            <div>
              <span className="text-[var(--text-secondary)]">Skill:</span>{" "}
              <span className="text-[var(--text-primary)]">{skill}</span>
            </div>
          )}
        </div>
      </div>

      <div>
        <label
          htmlFor="help-description"
          className="block text-sm font-medium text-[var(--text-secondary)] mb-2"
        >
          Describe the issue or question
        </label>
        <textarea
          id="help-description"
          value={description}
          onChange={(event) => onDescriptionChange(event.target.value)}
          placeholder="Be as specific as possible. What did you expect to happen? What happened instead?"
          rows={6}
          className="w-full px-4 py-3 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-transparent resize-none"
        />
        <div className="text-xs text-[var(--text-muted)] mt-1">
          {minLengthStatus}
        </div>
      </div>
    </div>
  );
}

export function BrowserErrorsPreview({ browserErrors }: { browserErrors: string[] }) {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-lg p-3 border border-[var(--border-color)]">
      <div className="text-xs uppercase text-[var(--text-muted)] mb-2 flex items-center gap-1.5">
        <Eye className="size-3" />
        Preview
      </div>
      <div className="space-y-2 max-h-40 overflow-y-auto">
        {browserErrors.map((err) => (
          <div
            key={err}
            className="text-xs font-mono text-[var(--accent-danger)] bg-[var(--accent-danger)]/5 rounded p-2 break-all"
          >
            {err.slice(0, 200)}
            {err.length > 200 && "..."}
          </div>
        ))}
      </div>
    </div>
  );
}

export function StepLogs({
  includeBrowserErrors,
  onIncludeBrowserErrorsChange,
  browserErrors,
  emailNotify,
  onEmailNotifyChange,
  userEmail,
  onUserEmailChange,
}: {
  includeBrowserErrors: boolean;
  onIncludeBrowserErrorsChange: (value: boolean) => void;
  browserErrors: string[];
  emailNotify: boolean;
  onEmailNotifyChange: (value: boolean) => void;
  userEmail: string;
  onUserEmailChange: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text-secondary)]">
        Optionally include diagnostic information to help resolve your issue
        faster.
      </p>

      <label
        className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
          includeBrowserErrors
            ? "border-[var(--accent-primary)]/50 bg-[var(--accent-primary)]/5"
            : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-[var(--text-muted)]"
        }`}
      >
        <input
          type="checkbox"
          checked={includeBrowserErrors}
          onChange={(event) =>
            onIncludeBrowserErrorsChange(event.target.checked)
          }
          className="mt-0.5 accent-[var(--accent-primary)]"
        />
        <div>
          <div className="text-sm font-medium text-[var(--text-primary)]">
            Include browser console errors
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-1">
            {browserErrors.length > 0
              ? `${browserErrors.length} error(s) detected`
              : "No errors detected in this session"}
          </div>
        </div>
      </label>

      {includeBrowserErrors && browserErrors.length > 0 && (
        <BrowserErrorsPreview browserErrors={browserErrors} />
      )}

      <label
        className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
          emailNotify
            ? "border-[var(--accent-primary)]/50 bg-[var(--accent-primary)]/5"
            : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-[var(--text-muted)]"
        }`}
      >
        <input
          type="checkbox"
          checked={emailNotify}
          onChange={(event) => onEmailNotifyChange(event.target.checked)}
          className="mt-0.5 accent-[var(--accent-primary)]"
        />
        <div className="flex-1">
          <div className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-1.5">
            <Mail className="size-3.5" />
            Email me when resolved
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-1">
            {"We'll only use it to notify you about this ticket."}
          </div>
          {emailNotify && (
            <input
              type="email"
              value={userEmail}
              onChange={(event) => onUserEmailChange(event.target.value)}
              placeholder="your@email.com"
              onClick={(event) => event.stopPropagation()}
              className="mt-2 w-full px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-transparent"
            />
          )}
        </div>
      </label>

      <div className="bg-[var(--bg-secondary)] rounded-lg p-3 border border-[var(--border-color)]">
        <div className="text-xs text-[var(--text-muted)]">
          All logs are stripped of personal information (file paths, API keys,
          emails) before being sent. You can review the final payload in the
          next step.
        </div>
      </div>
    </div>
  );
}

export function StepReview({
  strippedItems,
  previewPayload,
  consentGiven,
  onConsentChange,
  submitError,
}: {
  strippedItems: StrippedItem[];
  previewPayload: HelpPayload | null;
  consentGiven: boolean;
  onConsentChange: (value: boolean) => void;
  submitError: string | null;
}) {
  return (
    <div className="space-y-4">
      {strippedItems.length > 0 && (
        <div className="bg-[var(--accent-warning)]/10 rounded-lg p-3 border border-[var(--accent-warning)]/20">
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--accent-warning)] mb-2">
            <AlertTriangle className="size-3.5" />
            {strippedItems.length} item(s) were automatically redacted
          </div>
          <div className="space-y-1">
            {strippedItems.map((item) => (
              <div key={`${item.type}:${item.original}`} className="text-xs text-[var(--accent-warning)]/70">
                {item.type}: <span className="font-mono">{item.original}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-[var(--bg-secondary)] rounded-lg p-4 border border-[var(--border-color)]">
        <div className="text-xs uppercase text-[var(--text-muted)] mb-2">
          What will be sent
        </div>
        <pre className="text-xs font-mono text-[var(--text-secondary)] max-h-48 overflow-y-auto whitespace-pre-wrap break-all">
          {previewPayload
            ? JSON.stringify(previewPayload, null, 2)
            : "Building preview..."}
        </pre>
      </div>

      <label
        className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
          consentGiven
            ? "border-[var(--accent-success)]/50 bg-[var(--accent-success)]/5"
            : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-[var(--text-muted)]"
        }`}
      >
        <input
          type="checkbox"
          checked={consentGiven}
          onChange={(event) => onConsentChange(event.target.checked)}
          className="mt-0.5 accent-[var(--accent-success)]"
        />
        <div className="text-sm text-[var(--text-secondary)]">
          I confirm this data does not contain personal information I want to
          keep private. No API keys, passwords, or sensitive data are included.
        </div>
      </label>

      {submitError && (
        <div className="bg-[var(--accent-danger)]/10 rounded-lg p-3 border border-[var(--accent-danger)]/20">
          <div className="text-xs text-[var(--accent-danger)]">{submitError}</div>
        </div>
      )}
    </div>
  );
}

export function StepContent({
  step,
  topic,
  setTopic,
  pathname,
  skill,
  description,
  setDescription,
  includeBrowserErrors,
  setIncludeBrowserErrors,
  browserErrors,
  emailNotify,
  setEmailNotify,
  setUserEmail,
  userEmail,
  strippedItems,
  previewPayload,
  consentGiven,
  setConsentGiven,
  submitError,
}: {
  step: number;
  topic: HelpTopic | null;
  setTopic: (topic: HelpTopic) => void;
  pathname: string | null;
  skill: string | null;
  description: string;
  setDescription: (value: string) => void;
  includeBrowserErrors: boolean;
  setIncludeBrowserErrors: (value: boolean) => void;
  browserErrors: string[];
  emailNotify: boolean;
  setEmailNotify: (value: boolean) => void;
  userEmail: string;
  setUserEmail: (value: string) => void;
  strippedItems: StrippedItem[];
  previewPayload: HelpPayload | null;
  consentGiven: boolean;
  setConsentGiven: (value: boolean) => void;
  submitError: string | null;
}) {
  if (step === 1) {
    return <StepTopic topic={topic} onTopicChange={setTopic} />;
  }

  if (step === 2) {
    return (
      <StepDetails
        pathname={pathname}
        skill={skill}
        description={description}
        onDescriptionChange={setDescription}
      />
    );
  }

  if (step === 3) {
    return (
      <StepLogs
        includeBrowserErrors={includeBrowserErrors}
        onIncludeBrowserErrorsChange={setIncludeBrowserErrors}
        browserErrors={browserErrors}
        emailNotify={emailNotify}
        onEmailNotifyChange={(value) => {
          setEmailNotify(value);
          if (!value) {
            setUserEmail("");
          }
        }}
        userEmail={userEmail}
        onUserEmailChange={setUserEmail}
      />
    );
  }

  return (
    <StepReview
      strippedItems={strippedItems}
      previewPayload={previewPayload}
      consentGiven={consentGiven}
      onConsentChange={setConsentGiven}
      submitError={submitError}
    />
  );
}

export function FooterActions({
  step,
  canGoNext,
  onBack,
  onCancel,
  onNext,
  onSubmit,
  submitting,
}: {
  step: number;
  canGoNext: boolean;
  onBack: () => void;
  onCancel: () => void;
  onNext: () => void;
  onSubmit: () => void;
  submitting: boolean;
}) {
  const isLastStep = step === TOTAL_STEPS;

  return (
    <div className="flex items-center justify-between p-6 border-t border-[var(--border-color)]">
      <button type="button"
        onClick={step > 1 ? onBack : onCancel}
        className="px-4 py-2 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors flex items-center gap-1.5"
      >
        <ChevronLeft className="size-4" />
        {step === 1 ? "Cancel" : "Back"}
      </button>

      {!isLastStep && (
        <button type="button"
          onClick={onNext}
          disabled={!canGoNext}
          className="px-6 py-2 bg-[var(--accent-primary)] hover:opacity-90 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          Next
          <ChevronRight className="size-4" />
        </button>
      )}

      {isLastStep && (
        <button type="button"
          onClick={onSubmit}
          disabled={!canGoNext || submitting}
          className="px-6 py-2 bg-[var(--accent-primary)] hover:opacity-90 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {submitting ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Submitting…
            </>
          ) : (
            <>
              <Send className="size-4" />
              Submit Request
            </>
          )}
        </button>
      )}
    </div>
  );
}
