'use client';

import DashboardWidget from '@/features/components/DashboardWidget';
import { User, Edit3, Save, X, RefreshCw, Sparkles, CheckCircle, Target, ShieldCheck, AlertTriangle } from 'lucide-react';
import type { BrainOperationNotice, HumanApiProfile as HumanApiProfileType } from '../types';

interface HumanApiProfileProps {
  profile: HumanApiProfileType | null;
  editedProfile: HumanApiProfileType | null;
  setEditedProfile: (p: HumanApiProfileType | null) => void;
  isEditing: boolean;
  setIsEditing: (v: boolean) => void;
  isSaving: boolean;
  isRegenerating?: boolean;
  onSave: () => void;
  onRegenerate: () => void;
  onCancel: () => void;
  notice?: BrainOperationNotice | null;
  error?: string | null;
}

function OperationBanner({ notice, error }: { notice?: BrainOperationNotice | null; error?: string | null }) {
  if (!notice && !error) {
    return null;
  }

  return (
    <div className="mb-4 space-y-2">
      {notice && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs ${
            notice.type === 'success'
              ? 'border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--text-primary)]'
              : notice.type === 'error'
                ? 'border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--text-primary)]'
                : 'border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)]'
          }`}
          role={notice.type === 'error' ? 'alert' : 'status'}
        >
          {notice.message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--text-primary)]" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

function ProfileEmptyState({
  onRegenerate,
  isRegenerating = false,
}: {
  onRegenerate: () => void;
  isRegenerating?: boolean;
}) {
  return (
    <div className="text-center py-8">
      <Sparkles className="size-12 text-purple-400 mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">No Profile Yet</h3>
      <p className="text-sm text-[var(--text-muted)] mb-4">
        Generate your Human API Profile to help AI understand how to work with you effectively.
      </p>
      <button type="button"
        onClick={onRegenerate}
        disabled={isRegenerating}
        className="px-4 min-h-[44px] bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 rounded-lg text-[var(--accent-secondary)] transition-colors duration-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isRegenerating ? 'Generating...' : 'Generate Profile'}
      </button>
    </div>
  );
}

function ProfileHeader({
  lastUpdated,
  isEditing,
  isSaving,
  isRegenerating = false,
  setIsEditing,
  onSave,
  onRegenerate,
  onCancel,
}: {
  lastUpdated?: string;
  isEditing: boolean;
  isSaving: boolean;
  isRegenerating?: boolean;
  setIsEditing: (v: boolean) => void;
  onSave: () => void;
  onRegenerate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="min-w-0 text-sm text-[var(--text-muted)]">
        Auto-generated from session patterns. Last updated: {lastUpdated || 'Unknown'}
      </p>
      <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
        {isEditing ? (
          <>
            <button type="button"
              onClick={onCancel}
              className="flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-secondary)] transition-colors duration-200 hover:bg-[var(--bg-hover)] sm:flex-none"
            >
              <X className="size-3" aria-hidden="true" /> Cancel
            </button>
            <button type="button"
              onClick={onSave}
              disabled={isSaving}
              className="flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg border border-[var(--accent-success)]/30 bg-[var(--accent-success)]/20 px-3 text-sm text-[var(--accent-success)] transition-colors duration-200 hover:bg-[var(--accent-success)]/30 disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
            >
              <Save className="size-3" aria-hidden="true" /> {isSaving ? 'Saving...' : 'Save'}
            </button>
          </>
        ) : (
          <>
            <button type="button"
              onClick={() => setIsEditing(true)}
              className="flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-secondary)] transition-colors duration-200 hover:bg-[var(--bg-hover)] sm:flex-none"
            >
              <Edit3 className="size-3" aria-hidden="true" /> Edit
            </button>
            <button type="button"
              onClick={onRegenerate}
              disabled={isRegenerating}
              className="flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-lg border border-purple-500/30 bg-purple-500/20 px-3 text-sm text-[var(--accent-secondary)] transition-colors duration-200 hover:bg-purple-500/30 disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
            >
              <RefreshCw className={`size-3 ${isRegenerating ? 'animate-spin' : ''}`} aria-hidden="true" /> {isRegenerating ? 'Regenerating...' : 'Regenerate'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function IdentitySection({
  profile,
  editedProfile,
  isEditing,
  setEditedProfile,
}: {
  profile: HumanApiProfileType;
  editedProfile: HumanApiProfileType | null;
  isEditing: boolean;
  setEditedProfile: (p: HumanApiProfileType | null) => void;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <h4 className="text-sm font-medium text-purple-400 mb-3">Identity</h4>
      {isEditing && editedProfile ? (
        <div className="space-y-2">
          <label className="block">
            <span className="text-xs text-[var(--text-muted)]">Role</span>
            <input
              type="text"
              value={editedProfile.role}
              onChange={(e) => setEditedProfile({ ...editedProfile, role: e.target.value })}
              aria-label="Role"
              className="w-full mt-1 px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] transition-colors duration-200"
            />
          </label>
          <label className="block">
            <span className="text-xs text-[var(--text-muted)]">Expertise (comma-separated)</span>
            <input
              type="text"
              value={editedProfile.expertise.join(', ')}
              onChange={(e) =>
                setEditedProfile({
                  ...editedProfile,
                  expertise: e.target.value.split(',').flatMap((item) => {
                    const trimmed = item.trim();
                    return trimmed ? [trimmed] : [];
                  }),
                })
              }
              aria-label="Expertise, comma-separated"
              className="w-full mt-1 px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] transition-colors duration-200"
            />
          </label>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <div>
            <span className="text-[var(--text-muted)]">Role:</span>{' '}
            <span className="text-[var(--text-primary)]">{profile.role}</span>
          </div>
          <div>
            <span className="text-[var(--text-muted)]">Expertise:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {profile.expertise.map((expertise) => (
                <span key={expertise} className="px-2 py-0.5 bg-purple-500/20 text-[var(--accent-secondary)] rounded-full text-xs">
                  {expertise}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CommunicationSection({
  profile,
  editedProfile,
  isEditing,
  setEditedProfile,
}: {
  profile: HumanApiProfileType;
  editedProfile: HumanApiProfileType | null;
  isEditing: boolean;
  setEditedProfile: (p: HumanApiProfileType | null) => void;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <h4 className="text-sm font-medium text-emerald-400 mb-3">Communication Style</h4>
      {isEditing && editedProfile ? (
        <textarea
          value={editedProfile.communicationStyle}
          onChange={(e) => setEditedProfile({ ...editedProfile, communicationStyle: e.target.value })}
          aria-label="Communication style"
          className="w-full h-24 px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] transition-colors duration-200"
          placeholder="How do you prefer information? (format, tone, length)"
        />
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">{profile.communicationStyle || 'Not specified'}</p>
      )}
    </div>
  );
}

function SuccessCriteriaSection({
  profile,
  editedProfile,
  isEditing,
  setEditedProfile,
}: {
  profile: HumanApiProfileType;
  editedProfile: HumanApiProfileType | null;
  isEditing: boolean;
  setEditedProfile: (p: HumanApiProfileType | null) => void;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <h4 className="text-sm font-medium text-amber-400 mb-3">Success Criteria</h4>
      {isEditing && editedProfile ? (
        <textarea
          value={editedProfile.successCriteria.join('\n')}
          onChange={(e) =>
            setEditedProfile({
              ...editedProfile,
              successCriteria: e.target.value.split('\n').filter(Boolean),
            })
          }
          aria-label="Success criteria"
          className="w-full h-24 px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] transition-colors duration-200"
          placeholder="What makes a response 'good'? (one per line)"
        />
      ) : (
        <ul className="text-sm text-[var(--text-secondary)] space-y-1">
          {profile.successCriteria.map((criteria) => (
            <li key={criteria} className="flex items-start gap-2">
              <CheckCircle className="size-3 text-amber-400 mt-1 flex-shrink-0" aria-hidden="true" />
              {criteria}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ContextGapsSection({
  profile,
  editedProfile,
  isEditing,
  setEditedProfile,
}: {
  profile: HumanApiProfileType;
  editedProfile: HumanApiProfileType | null;
  isEditing: boolean;
  setEditedProfile: (p: HumanApiProfileType | null) => void;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <h4 className="text-sm font-medium text-pink-400 mb-3">Context Gaps (What to Ask About)</h4>
      {isEditing && editedProfile ? (
        <textarea
          value={editedProfile.contextGaps.join('\n')}
          onChange={(e) =>
            setEditedProfile({
              ...editedProfile,
              contextGaps: e.target.value.split('\n').filter(Boolean),
            })
          }
          aria-label="Context gaps"
          className="w-full h-24 px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] transition-colors duration-200"
          placeholder="What context should AI ask about? (one per line)"
        />
      ) : (
        <ul className="text-sm text-[var(--text-secondary)] space-y-1">
          {profile.contextGaps.map((gap) => (
            <li key={gap} className="flex items-start gap-2">
              <Target className="size-3 text-pink-400 mt-1 flex-shrink-0" aria-hidden="true" />
              {gap}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function getProfileFields(profile: HumanApiProfileType) {
  return [
    { id: 'role', label: 'Role', complete: Boolean(profile.role.trim()) },
    { id: 'expertise', label: 'Expertise', complete: profile.expertise.length > 0 },
    { id: 'communicationStyle', label: 'Communication style', complete: Boolean(profile.communicationStyle.trim()) },
    { id: 'successCriteria', label: 'Success criteria', complete: profile.successCriteria.length > 0 },
    { id: 'contextGaps', label: 'Context gaps', complete: profile.contextGaps.length > 0 },
  ];
}

function getConfidenceLabel(profile: HumanApiProfileType) {
  const fields = getProfileFields(profile);
  const completeCount = fields.filter((field) => field.complete).length;
  if (!profile.role.trim() || profile.successCriteria.length === 0) {
    return 'Low';
  }
  if (completeCount >= 4) return 'High';
  if (completeCount >= 3) return 'Medium';
  return 'Low';
}

function ProfileProvenancePanel({
  profile,
  setIsEditing,
}: {
  profile: HumanApiProfileType;
  setIsEditing: (v: boolean) => void;
}) {
  const fields = getProfileFields(profile);
  const missingFields = fields.filter((field) => !field.complete);
  const rawLines = profile.rawContent ? profile.rawContent.split('\n').filter((line) => line.trim()).length : 0;

  return (
    <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-[1.2fr_1fr]">
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-cyan-400" aria-hidden="true" />
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">Profile provenance</h4>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-[var(--text-muted)] sm:grid-cols-3">
          <div>
            <span className="block font-medium text-[var(--text-secondary)]">Source</span>
            knowledge-memory-profile
          </div>
          <div>
            <span className="block font-medium text-[var(--text-secondary)]">Last updated</span>
            {profile.lastUpdated || 'Unknown'}
          </div>
          <div>
            <span className="block font-medium text-[var(--text-secondary)]">Evidence</span>
            {rawLines} markdown lines parsed
          </div>
        </div>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          Profile confidence: {getConfidenceLabel(profile)}
        </p>
      </div>

      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="size-4 text-amber-400" aria-hidden="true" />
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">Missing fields</h4>
        </div>
        {missingFields.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {missingFields.map((field) => (
              <button
                key={field.id}
                type="button"
                onClick={() => setIsEditing(true)}
                className="inline-flex min-h-[44px] items-center rounded-md border border-[var(--border-color)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
              >
                Add {field.label.toLowerCase()}
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            All core profile fields are populated from the current Human API file.
          </p>
        )}
      </div>
    </div>
  );
}

export function HumanApiProfile({
  profile,
  editedProfile,
  setEditedProfile,
  isEditing,
  setIsEditing,
  isSaving,
  isRegenerating = false,
  onSave,
  onRegenerate,
  onCancel,
  notice,
  error,
}: HumanApiProfileProps) {
  return (
    <DashboardWidget title="Human API Profile" icon={User} fillHeight={false}>
      <div className="p-4">
        <OperationBanner notice={notice} error={error} />
        {!profile?.exists && <ProfileEmptyState onRegenerate={onRegenerate} isRegenerating={isRegenerating} />}
        {profile?.exists && (
          <>
            <ProfileHeader
              lastUpdated={profile.lastUpdated ?? undefined}
              isEditing={isEditing}
              isSaving={isSaving}
              isRegenerating={isRegenerating}
              setIsEditing={setIsEditing}
              onSave={onSave}
              onRegenerate={onRegenerate}
              onCancel={onCancel}
            />

            <ProfileProvenancePanel profile={profile} setIsEditing={setIsEditing} />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <IdentitySection
                profile={profile}
                editedProfile={editedProfile}
                isEditing={isEditing}
                setEditedProfile={setEditedProfile}
              />
              <CommunicationSection
                profile={profile}
                editedProfile={editedProfile}
                isEditing={isEditing}
                setEditedProfile={setEditedProfile}
              />
              <SuccessCriteriaSection
                profile={profile}
                editedProfile={editedProfile}
                isEditing={isEditing}
                setEditedProfile={setEditedProfile}
              />
              <ContextGapsSection
                profile={profile}
                editedProfile={editedProfile}
                isEditing={isEditing}
                setEditedProfile={setEditedProfile}
              />
            </div>
          </>
        )}
      </div>
    </DashboardWidget>
  );
}
