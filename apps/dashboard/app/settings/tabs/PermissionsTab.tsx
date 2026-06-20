"use client";

import { useState } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import {
  Key,
  Monitor,
  Mic,
  Hand,
  Calendar,
  StickyNote,
  Mail,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Package,
  ExternalLink,
  Info,
  Camera,
  MapPin,
  Bell,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

type PermissionStatus = "granted" | "denied" | "unknown" | "not_configured";
type PermissionCategory =
  | "macos_system"
  | "windows_system"
  | "email_calendar"
  | "dependencies";

interface Permission {
  id: string;
  name: string;
  status: PermissionStatus;
  description: string;
  category: PermissionCategory;
  instructions: string;
  deepLink?: string;
}

// Deep links to System Settings panes (macOS)
const MACOS_DEEP_LINKS: Record<string, string> = {
  screen_recording:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
  microphone:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
  accessibility:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
  calendar:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars",
  apple_notes:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
  apple_mail:
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
};

// Deep links to Windows Settings (ms-settings: URIs)
const WINDOWS_DEEP_LINKS: Record<string, string> = {
  microphone: "ms-settings:privacy-microphone",
  camera: "ms-settings:privacy-webcam",
  location: "ms-settings:privacy-location",
  calendar: "ms-settings:privacy-calendar",
  notifications: "ms-settings:notifications",
};

const CATEGORY_CONFIG: Record<
  PermissionCategory,
  { title: string; icon: typeof Monitor; color: string; description: string }
> = {
  macos_system: {
    title: "macOS System Permissions",
    icon: Monitor,
    color: "text-[var(--accent-primary)]",
    description:
      "These permissions are managed in System Settings > Privacy & Security",
  },
  windows_system: {
    title: "Windows System Permissions",
    icon: Monitor,
    color: "text-[var(--accent-info)]",
    description:
      "These permissions are managed in Settings > Privacy & security",
  },
  email_calendar: {
    title: "Email & Calendar",
    icon: Calendar,
    color: "text-[var(--accent-secondary)]",
    description: "Integration with email services and calendar apps",
  },
  dependencies: {
    title: "System Dependencies",
    icon: Package,
    color: "text-[var(--accent-warning)]",
    description: "External tools required for full functionality",
  },
};

const STATUS_CONFIG = {
  granted: {
    icon: CheckCircle2,
    color: "text-[var(--accent-success)]",
    bg: "bg-[var(--accent-success)]/10",
    border: "border-[var(--accent-success)]/30",
    label: "Granted",
  },
  denied: {
    icon: XCircle,
    color: "text-[var(--accent-danger)]",
    bg: "bg-[var(--accent-danger)]/10",
    border: "border-[var(--accent-danger)]/30",
    label: "Denied",
  },
  unknown: {
    icon: AlertCircle,
    color: "text-[var(--accent-warning)]",
    bg: "bg-[var(--accent-warning)]/10",
    border: "border-[var(--accent-warning)]/30",
    label: "Unknown",
  },
  not_configured: {
    icon: AlertCircle,
    color: "text-[var(--text-muted)]",
    bg: "bg-[var(--text-muted)]/10",
    border: "border-[var(--text-muted)]/30",
    label: "Not Configured",
  },
};

const PERMISSION_ICONS: Record<string, typeof Key> = {
  screen_recording: Monitor,
  microphone: Mic,
  accessibility: Hand,
  calendar: Calendar,
  apple_notes: StickyNote,
  apple_mail: Mail,
  email_imap: Mail,
  tesseract: FileText,
  // Windows-specific
  camera: Camera,
  location: MapPin,
  notifications: Bell,
};

function PermissionRow({
  permission,
  platform,
}: {
  permission: Permission;
  platform: string | null;
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const statusConfig = STATUS_CONFIG[permission.status];
  const StatusIcon = statusConfig.icon;
  const PermIcon = PERMISSION_ICONS[permission.id] || Key;

  // Select the correct deep link based on platform
  const deepLink =
    platform === "win32"
      ? WINDOWS_DEEP_LINKS[permission.id]
      : MACOS_DEEP_LINKS[permission.id];

  const handleOpenSettings = () => {
    if (deepLink) {
      window.open(deepLink, "_blank");
    }
  };

  return (
    <div
      className={`glass-panel p-4 ${statusConfig.bg} border-l-4 ${statusConfig.border} relative transition-colors duration-200 hover:bg-[var(--bg-hover)] focus-within:bg-[var(--bg-hover)]`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <PermIcon className="size-5 text-[var(--text-muted)] mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-[var(--text-primary)]">
                {permission.name}
              </h3>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${statusConfig.bg} ${statusConfig.color}`}
              >
                <StatusIcon className="size-3" />
                {statusConfig.label}
              </span>
              <button
                type="button"
                className="inline-flex items-center justify-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
                aria-label={`More info about ${permission.name}`}
                onFocus={() => setShowTooltip(true)}
                onBlur={() => setShowTooltip(false)}
              >
                <Info className="size-3.5 text-[var(--text-muted)] cursor-help" />
              </button>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {permission.description}
            </p>
          </div>
        </div>
        {/* Open Settings button for macOS permissions */}
        {deepLink &&
          (permission.status === "denied" ||
            permission.status === "unknown") && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenSettings}
              className="shrink-0"
              leftIcon={<ExternalLink className="size-3.5" />}
            >
              Open Settings
            </Button>
          )}
      </div>

      {/* Tooltip on hover - only show for non-granted permissions */}
      {showTooltip && permission.status !== "granted" && (
        <div className="absolute left-0 right-0 -bottom-2 transform translate-y-full z-20 px-4">
          <div className="p-3 rounded-lg bg-[var(--bg-popover)] border border-[var(--border-color)] shadow-xl">
            <p className="text-xs text-[var(--text-secondary)]">
              <span className="font-medium text-[var(--accent-primary)]">
                How to enable:
              </span>{" "}
              {permission.instructions}
            </p>
          </div>
        </div>
      )}

      {/* Expanded instructions for denied/not_configured (always visible) */}
      {(permission.status === "denied" ||
        permission.status === "not_configured") && (
        <div className="mt-3 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
          <p className="text-xs text-[var(--text-secondary)]">
            <span className="font-medium">How to fix:</span>{" "}
            {permission.instructions}
          </p>
        </div>
      )}
    </div>
  );
}

function CategorySection({
  category,
  permissions,
  platform,
}: {
  category: PermissionCategory;
  permissions: Permission[];
  platform: string | null;
}) {
  const config = CATEGORY_CONFIG[category];
  const Icon = config.icon;

  if (permissions.length === 0) return null;

  return (
    <section>
      <div className="flex items-center gap-3 mb-4">
        <Icon className={`size-5 ${config.color}`} />
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
            {config.title}
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            {config.description}
          </p>
        </div>
      </div>
      <div className="grid gap-3">
        {permissions.map((perm) => (
          <PermissionRow key={perm.id} permission={perm} platform={platform} />
        ))}
      </div>
    </section>
  );
}

interface PermissionsApiResponse {
  ok: boolean;
  permissions?: Permission[];
  platform?: string;
  error?: string;
}

export default function PermissionsTab() {
  const {
    data: permData,
    loading,
    error: fetchError,
    refetch: fetchPermissions,
  } = useMcpQuery<PermissionsApiResponse>(
    "permissions-status",
    "check-system-permissions",
    "config",
  );

  const permissions = permData?.ok ? (permData.permissions ?? []) : [];
  const platform = permData?.platform ?? null;
  const error =
    fetchError ||
    (permData && !permData.ok
      ? permData.error || "Failed to fetch permissions"
      : null);

  const macosPermissions = permissions.filter(
    (p) => p.category === "macos_system",
  );
  const windowsPermissions = permissions.filter(
    (p) => p.category === "windows_system",
  );
  const emailPermissions = permissions.filter(
    (p) => p.category === "email_calendar",
  );
  const depPermissions = permissions.filter(
    (p) => p.category === "dependencies",
  );

  const grantedCount = permissions.filter((p) => p.status === "granted").length;
  const unknownCount = permissions.filter(
    (p) => p.status === "unknown",
  ).length;
  const issueCount = permissions.filter(
    (p) => p.status === "denied" || p.status === "not_configured",
  ).length;

  return (
    <div className="space-y-8 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-500">
      {/* Header with refresh and stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Key className="size-5 text-[var(--accent-primary)]" />
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
              System Permissions
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Manage permissions required by Augur features
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchPermissions}
          disabled={loading}
          aria-label="Refresh permissions"
          leftIcon={<RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />}
        >
          Refresh
        </Button>
      </div>

      {/* Stats row — Granted + Unverified + Need Attention reconcile to Total */}
      {!loading && permissions.length > 0 && (
        <div
          className={`grid grid-cols-1 gap-4 ${unknownCount > 0 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-3"}`}
        >
          <div className="glass-panel p-4 text-center">
            <div className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">
              {permissions.length}
            </div>
            <div className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mt-1">
              Total Permissions
            </div>
          </div>
          <div className="glass-panel p-4 text-center bg-[var(--accent-success)]/5">
            <div className="text-2xl font-semibold text-[var(--accent-success)] tracking-tight">
              {grantedCount}
            </div>
            <div className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mt-1">
              Granted
            </div>
          </div>
          {unknownCount > 0 && (
            <div className="glass-panel p-4 text-center">
              <div className="text-2xl font-semibold text-[var(--text-muted)] tracking-tight">
                {unknownCount}
              </div>
              <div className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mt-1">
                Unverified
              </div>
            </div>
          )}
          <div
            className={`glass-panel p-4 text-center ${issueCount > 0 ? "bg-[var(--accent-warning)]/5" : ""}`}
          >
            <div
              className={`text-2xl font-semibold ${issueCount > 0 ? "text-[var(--accent-warning)]" : "text-[var(--text-muted)]"} tracking-tight`}
            >
              {issueCount}
            </div>
            <div className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mt-1">
              Need Attention
            </div>
          </div>
        </div>
      )}

      {/* Unsupported platform warning */}
      {platform && platform !== "darwin" && platform !== "win32" && (
        <div className="glass-panel p-6 border border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/10">
          <div className="flex items-center gap-3">
            <AlertCircle className="size-5 text-[var(--accent-warning)]" />
            <div>
              <h3 className="font-medium text-[var(--text-primary)]">
                Unsupported Platform
              </h3>
              <p className="text-sm text-[var(--text-secondary)]">
                Permission checks are only available on macOS and Windows.
                Current platform: {platform}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="h-20 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
              />
            ))}
          </div>
          <div className="grid gap-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-20 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
              />
            ))}
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="glass-panel p-6 border border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <XCircle className="size-5 text-[var(--accent-danger)] shrink-0" />
              <div>
                <h3 className="font-medium text-[var(--text-primary)]">Error</h3>
                <p className="text-sm text-[var(--text-secondary)]">{error}</p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchPermissions}
              className="shrink-0"
              leftIcon={<RefreshCw className="size-4" />}
            >
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Permission sections */}
      {!loading && !error && (
        <>
          <CategorySection
            category="macos_system"
            permissions={macosPermissions}
            platform={platform}
          />
          <CategorySection
            category="windows_system"
            permissions={windowsPermissions}
            platform={platform}
          />
          <CategorySection
            category="email_calendar"
            permissions={emailPermissions}
            platform={platform}
          />
          <CategorySection
            category="dependencies"
            permissions={depPermissions}
            platform={platform}
          />
        </>
      )}
    </div>
  );
}
