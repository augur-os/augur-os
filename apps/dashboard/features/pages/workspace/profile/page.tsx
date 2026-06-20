'use client';

import { User } from 'lucide-react';
import { VoiceProfile } from './components/VoiceProfile';
import { HumanApiProfile } from '../memory/components/HumanApiProfile';
import { useMemoryWorkspace, useProfile } from '../memory/hooks';

export default function MemoryProfilePage() {
  const profileHook = useProfile();
  const { refreshWorkspace } = useMemoryWorkspace();

  const handleSaveProfile = async () => {
    const saved = await profileHook.saveProfile();
    if (saved) {
      await refreshWorkspace();
    }
  };

  const handleRegenerateProfile = async () => {
    const regenerated = await profileHook.regenerateProfile();
    if (regenerated) {
      await refreshWorkspace();
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-3">
        <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/10 p-3">
          <User className="size-5 text-cyan-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Memory Profile</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Review, edit, and regenerate the human API profile in a dedicated view.
          </p>
        </div>
      </header>

      <VoiceProfile />

      <HumanApiProfile
        profile={profileHook.profile}
        editedProfile={profileHook.editedProfile}
        setEditedProfile={profileHook.setEditedProfile}
        isEditing={profileHook.isEditing}
        setIsEditing={profileHook.setIsEditing}
        isSaving={profileHook.isSaving}
        isRegenerating={profileHook.isRegenerating}
        onSave={handleSaveProfile}
        onRegenerate={handleRegenerateProfile}
        onCancel={profileHook.cancelEdit}
        notice={profileHook.notice}
        error={profileHook.error}
      />
    </div>
  );
}
