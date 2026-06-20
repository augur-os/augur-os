"use client";

import { type ReactNode } from "react";
import {
  X,
  Send,
  Paperclip,
  FileText,
  ImageIcon,
  MessageSquare,
  Copy,
} from "lucide-react";
import { formatFileSize } from "@/components/chat/utils";
import type {
  FloatingChatMessage,
  FloatingChatAttachedFile,
  SuggestedAction,
} from "./types";

function getFileExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts.at(-1)?.toLowerCase() || "" : "";
}

function getFileTypeBadge(fileName: string): string {
  const extension = getFileExtension(fileName);

  if (!extension) return "FILE";
  if (["jpeg", "jpg", "png", "gif", "webp", "svg", "heic"].includes(extension)) {
    return "IMG";
  }
  if (extension === "markdown") return "MD";
  return extension.slice(0, 4).toUpperCase();
}

function getAttachmentSummary(attachedFiles: FloatingChatAttachedFile[]): string {
  const count = attachedFiles.length;
  const totalSize = attachedFiles.reduce((sum, file) => sum + file.size, 0);
  return `${count} file${count === 1 ? "" : "s"} attached · ${formatFileSize(totalSize)}`;
}

function parseFencedSetupHint(content: string):
  | { prefix: string; command: string }
  | null {
  const match = content.match(/([\s\S]*?)```(?:[a-zA-Z0-9_-]+)?\n([\s\S]*?)\n```/);
  if (!match) return null;

  const command = match[2].trim();
  if (!command) return null;

  return {
    prefix: match[1].replace(/\s+/g, " ").trim(),
    command,
  };
}

function SystemMessagePreview({ message }: { message: FloatingChatMessage }) {
  const setupHint = parseFencedSetupHint(message.content);

  if (!setupHint) {
    return (
      <div className="truncate border-t border-[var(--border-color)]/70 bg-[var(--bg-secondary)]/70 px-3 py-1 text-[11px] not-italic text-[var(--text-secondary)]">
        {message.content}
      </div>
    );
  }

  const copyHint = () => {
    navigator.clipboard?.writeText(setupHint.command).catch(() => {});
  };

  return (
    <div className="flex min-h-9 items-center gap-2 border-t border-[var(--border-color)]/70 bg-[var(--bg-secondary)]/70 px-3 py-1 text-[11px] not-italic text-[var(--text-secondary)]">
      <span className="min-w-0 flex-1 truncate">{setupHint.prefix}</span>
      <code className="max-w-[18rem] shrink truncate rounded-md border border-[var(--border-color)]/70 bg-[var(--bg-primary)]/80 px-2 py-1 font-mono text-[10px] text-[var(--text-primary)]">
        {setupHint.command}
      </code>
      <button
        type="button"
        onClick={copyHint}
        className="flex size-7 shrink-0 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-primary)]/80 hover:text-[var(--text-primary)]"
        aria-label="Copy setup hint"
        title="Copy setup hint"
      >
        <Copy className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

function FileTypeIcon({ fileName }: { fileName: string }) {
  const extension = getFileExtension(fileName);

  if (["jpeg", "jpg", "png", "gif", "webp", "svg", "heic"].includes(extension)) {
    return <ImageIcon className="size-3.5" aria-hidden="true" />;
  }

  return <FileText className="size-3.5" aria-hidden="true" />;
}

export function WelcomeOverlay({
  suggestedActions,
  onSelectAction,
}: {
  suggestedActions: SuggestedAction[];
  onSelectAction: (action: SuggestedAction) => void;
}) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[var(--bg-primary)]">
      <MessageSquare className="size-10 text-[var(--text-muted)] opacity-30 mb-4" />
      <p className="text-base font-medium text-[var(--text-primary)] mb-1">
        Ask me anything
      </p>
      <p className="text-xs text-[var(--text-muted)] mb-6 text-center max-w-[280px]">
        {suggestedActions.length > 0
          ? "Type a message below or pick a suggested action"
          : "Type a message below — the assistant starts on send"}
      </p>

      {suggestedActions.length > 0 && (
        <div className="flex flex-wrap gap-2 justify-center max-w-[320px]">
          {suggestedActions.slice(0, 3).map((action) => {
            const Icon = action.icon;
            return (
              <button type="button"
                key={`${action.toolName}-${action.label}`}
                onClick={() => onSelectAction(action)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg
                  bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border-color)]
                  text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                  transition-all duration-150"
              >
                {Icon && <Icon className="size-3.5" aria-hidden="true" />}
                <span>{action.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TerminalInputSection({
  handleSubmit,
  toolbarButtons,
  pathname,
  fileInputRef,
  handleFileSelect,
  handlePaste,
  textareaRef,
  input,
  handleTextareaChange,
  handleTextareaKeyDown,
  isRunning,
  isOperationMode,
  attachedFiles,
  removeAttachedFile,
  isDragOver,
  draft = false,
}: {
  handleSubmit: (e: React.FormEvent) => void;
  toolbarButtons: ReactNode;
  pathname: string;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handlePaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  input: string;
  handleTextareaChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleTextareaKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  isRunning: boolean;
  isOperationMode: boolean;
  attachedFiles: FloatingChatAttachedFile[];
  removeAttachedFile: (path: string) => void;
  isDragOver: boolean;
  // Draft mode (ADR-748 follow-up): a Browse AI action prefilled an editable
  // prompt before any CLI is running \u2014 keep the input usable and let send start
  // the CLI (see handleSubmit). Existing flows pass draft=false (unchanged).
  draft?: boolean;
}) {
  const canSend = input.trim().length > 0;
  const placeholder = isOperationMode
    ? "Message..."
    : isRunning
      ? "Type a command..."
      : draft
        ? "Review, edit, then send..."
        : "Type a message — the assistant starts on send...";

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-[var(--border-color)]/70 bg-[var(--bg-card)]/94 backdrop-blur-xl"
    >
      <div className="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
        <div
          data-testid="chat-toolbar-rail"
          className="flex items-center gap-1 rounded-full border border-[var(--border-color)]/70 bg-[var(--bg-primary)]/70 p-1"
        >
          {toolbarButtons}
        </div>
        {!isOperationMode && (
          <span className="ml-auto max-w-[12rem] truncate rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-primary)]/55 px-2 py-1 text-[10px] text-[var(--text-muted)]">
            {pathname}
          </span>
        )}
      </div>

      <div className="px-3 pb-3">
        <div
          className={`rounded-2xl border px-2.5 py-2 shadow-sm transition-all ${
            isDragOver
              ? "border-[var(--accent-primary)]/60 bg-[var(--accent-primary)]/10 ring-1 ring-[var(--accent-primary)]/25"
              : "border-[var(--border-color)]/70 bg-[var(--bg-primary)]/60"
          }`}
        >
          {attachedFiles.length > 0 && (
            <div className="mb-2 space-y-2">
              <div className="flex items-center justify-between gap-2 px-1">
                <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                  {getAttachmentSummary(attachedFiles)}
                </span>
                <span className="text-[11px] text-[var(--text-muted)]">
                  Ready to send
                </span>
              </div>
              <div
                data-testid="composer-attachments-tray"
                className="flex flex-nowrap gap-1.5 overflow-x-auto pb-1 pr-1"
              >
                {attachedFiles.map((file) => (
                  <span
                    key={file.stagedPath}
                    className="inline-flex max-w-[220px] shrink-0 items-center gap-2 rounded-2xl border border-[var(--border-color)]/70 bg-[var(--bg-card)]/90 px-2.5 py-1.5 text-xs text-[var(--text-secondary)]"
                  >
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-xl bg-[var(--bg-primary)] text-[var(--text-muted)]">
                      <FileTypeIcon fileName={file.originalName} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-[var(--text-primary)]">
                        {file.originalName}
                      </span>
                      <span className="block text-[10px] text-[var(--text-muted)]">
                        {formatFileSize(file.size)}
                      </span>
                    </span>
                    <span className="rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-primary)]/80 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-[var(--text-muted)]">
                      {getFileTypeBadge(file.originalName)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeAttachedFile(file.stagedPath)}
                      className="ml-0.5 text-[var(--text-muted)] transition-colors hover:text-red-400"
                      aria-label={`Remove ${file.originalName}`}
                    >
                      <X className="size-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div
            data-testid="chat-composer-main-row"
            className="flex items-end gap-1.5 px-1 py-0.5"
          >
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex size-9 flex-shrink-0 items-center justify-center rounded-full border border-transparent bg-[var(--bg-primary)]/65 text-[var(--text-muted)] transition-colors hover:border-[var(--border-color)]/70 hover:text-[var(--text-primary)]"
              title="Attach file"
              aria-label="Attach file"
            >
              <Paperclip className="size-4" aria-hidden="true" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileSelect}
              aria-label="Select files to attach"
            />

            <div className="min-w-0 flex-1 transition-all">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleTextareaChange}
                onKeyDown={handleTextareaKeyDown}
                onPaste={handlePaste}
                placeholder={placeholder}
                aria-label="Chat message input"
                rows={1}
                className="w-full resize-none overflow-y-auto bg-transparent p-2 text-sm leading-relaxed text-[var(--text-primary)] placeholder:text-[var(--text-muted)] !outline-none disabled:opacity-50"
                style={{ maxHeight: "200px", minHeight: "48px" }}
              />
            </div>

            {!isOperationMode && (
              <kbd
                className="hidden flex-shrink-0 select-none items-center gap-0.5 px-1 text-[10px] font-mono text-[var(--text-muted)] sm:inline-flex"
                title="Enter to send · Shift+Enter for a new line"
              >
                ↵
              </kbd>
            )}

            <button
              type="submit"
              disabled={!canSend}
              className="flex size-10 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent-primary)] text-[var(--accent-foreground)] shadow-md transition-all hover:scale-105 hover:opacity-90 active:scale-95 disabled:scale-100 disabled:cursor-not-allowed disabled:opacity-25 disabled:shadow-none"
              title="Send (Enter)"
              aria-label="Send message"
            >
              <Send className="size-4" />
            </button>
          </div>

          {isDragOver && (
            <div className="mt-2 flex items-center gap-2 pl-1">
              <span className="text-[11px] font-medium text-[var(--accent-primary)]">
                Drop files to attach them
              </span>
            </div>
          )}
        </div>
      </div>
    </form>
  );
}

export function TerminalBottomSection({
  chatView,
  terminalFocused,
  latestSystemMsg,
  inputSection,
  isOperationMode,
  focusStrip,
}: {
  chatView: string;
  terminalFocused: boolean;
  latestSystemMsg?: FloatingChatMessage;
  inputSection: ReactNode;
  isOperationMode?: boolean;
  focusStrip?: ReactNode;
}) {
  if (chatView !== "terminal" || terminalFocused) return null;

  return (
    <>
      {latestSystemMsg && !isOperationMode && (
        <SystemMessagePreview message={latestSystemMsg} />
      )}

      {focusStrip}
      {inputSection}
    </>
  );
}

export function TerminalFocusStrip({
  show,
  onExit,
}: {
  show: boolean;
  onExit: () => void;
}) {
  if (!show) return null;

  return (
    <div
      className="px-3 py-2 border-t border-[var(--border-color)] bg-[var(--accent-primary)]/10 flex items-center justify-between"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <span className="size-2 rounded-full bg-[var(--accent-primary)] motion-safe:animate-pulse" />
        <span className="text-xs font-medium text-[var(--accent-primary)]">
          Terminal Focus
        </span>
        <span className="text-xs text-[var(--text-muted)]">
          Keyboard input goes directly to terminal
        </span>
      </div>
      <button type="button"
        onClick={onExit}
        className="text-xs px-2 py-1 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        Esc to exit
      </button>
    </div>
  );
}
