/**
 * Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI.
 */

"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "./ui/Button";
import { emitClientError } from "@/lib/self-heal-event";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  resetOnChange?: unknown;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });

    // Log to console
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // Call optional error handler
    this.props.onError?.(error, errorInfo);

    // Report to self-heal pipeline (ADR-167)
    this.reportToTelemetry(error, errorInfo);
  }

  private reportToTelemetry(error: Error, errorInfo: ErrorInfo) {
    emitClientError({
      level: "error",
      message: error.message?.slice(0, 500) || "Unknown error",
      source: "error-boundary",
      url: typeof window !== "undefined" ? window.location.pathname : "",
      stack: error.stack?.slice(0, 1000),
      component: errorInfo.componentStack?.slice(0, 500),
      timestamp: new Date().toISOString(),
      fingerprint: `eb-${error.message?.slice(0, 100)}`,
      count: 1,
    });
  }

  public componentDidUpdate(prevProps: Props) {
    if (this.props.resetOnChange !== prevProps.resetOnChange) {
      this.reset();
    }
  }

  private reset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = "/";
  };

  public render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-[400px] flex items-center justify-center p-8">
          <div className="max-w-md w-full text-center space-y-6">
            {/* Error Icon */}
            <div className="size-16 mx-auto rounded-full bg-[var(--accent-danger)]/10 flex items-center justify-center">
              <AlertTriangle className="size-8 text-[var(--accent-danger)]" />
            </div>

            {/* Error Message */}
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-[var(--text-primary)]">
                Something went wrong
              </h2>
              <p className="text-sm text-[var(--text-muted)]">
                We apologize for the inconvenience. An unexpected error has
                occurred.
              </p>
            </div>

            {/* Error Details (collapsed) */}
            {process.env.NODE_ENV === "development" && this.state.error && (
              <details className="text-left">
                <summary className="cursor-pointer text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                  Error Details (Development Only)
                </summary>
                <div className="mt-2 p-3 rounded-lg bg-[var(--bg-secondary)] text-left overflow-auto max-h-48">
                  <p className="text-xs font-mono text-[var(--accent-danger)] mb-2">
                    {this.state.error.toString()}
                  </p>
                  {this.state.errorInfo && (
                    <pre className="text-xs font-mono text-[var(--text-muted)] whitespace-pre-wrap">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </div>
              </details>
            )}

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                variant="solid"
                leftIcon={<RefreshCw className="size-4" />}
                onClick={this.reset}
              >
                Try Again
              </Button>
              <Button
                variant="outline"
                leftIcon={<Home className="size-4" />}
                onClick={this.handleGoHome}
              >
                Go Home
              </Button>
            </div>

            {/* Reload Link */}
            <button type="button"
              onClick={this.handleReload}
              className="text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] underline py-1 px-2 min-h-[44px] inline-flex items-center"
            >
              Reload the page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Hub-specific error boundary with navigation back to hub
 */
interface HubErrorBoundaryProps extends Props {
  hubName: string;
  hubHref: string;
}

class HubErrorBoundary extends Component<HubErrorBoundaryProps, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error(
      `HubErrorBoundary (${this.props.hubName}) caught an error:`,
      error,
      errorInfo,
    );
    this.props.onError?.(error, errorInfo);

    // Report to self-heal pipeline (ADR-167)
    emitClientError({
      level: "error",
      message: error.message?.slice(0, 500) || "Unknown error",
      source: "error-boundary",
      url: typeof window !== "undefined" ? window.location.pathname : "",
      stack: error.stack?.slice(0, 1000),
      component: `Hub:${this.props.hubName} ${errorInfo.componentStack?.slice(0, 400) || ""}`,
      timestamp: new Date().toISOString(),
      fingerprint: `heb-${this.props.hubName}-${error.message?.slice(0, 80)}`,
      count: 1,
    });
  }

  private handleGoToHub = () => {
    window.location.href = this.props.hubHref;
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8">
          <div className="glass-panel p-6 text-center space-y-4">
            <AlertTriangle className="size-12 mx-auto text-[var(--accent-warning)]" />
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              {this.props.hubName} encountered an error
            </h2>
            <p className="text-sm text-[var(--text-muted)]">
              There was a problem loading this section. You can try again or
              return to the {this.props.hubName} overview.
            </p>
            <div className="flex gap-3 justify-center">
              <Button
                variant="outline"
                onClick={() => this.setState({ hasError: false })}
              >
                Try Again
              </Button>
              <Button variant="solid" onClick={this.handleGoToHub}>
                Go to {this.props.hubName}
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * API Error Fallback Component
 */
interface APIErrorFallbackProps {
  error: Error;
  reset: () => void;
  retry?: () => void;
}

function APIErrorFallback({
  error,
  reset,
  retry,
}: APIErrorFallbackProps) {
  return (
    <div className="p-6 text-center space-y-4">
      <AlertTriangle className="size-10 mx-auto text-[var(--accent-warning)]" />
      <div>
        <h3 className="text-base font-medium text-[var(--text-primary)]">
          Failed to load data
        </h3>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          {error.message || "An error occurred while fetching data."}
        </p>
      </div>
      <div className="flex gap-2 justify-center">
        {retry && (
          <Button variant="solid" size="sm" onClick={retry}>
            Retry
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={reset}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}


