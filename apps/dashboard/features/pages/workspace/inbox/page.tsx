"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { InboxHealthStrip } from "./components";
import { useBrainInbox } from "./hooks";
import { LatestRunList } from "./inbox.rows";
import {
  AddFolderSection,
  AddMailDropSection,
  InboxNotice,
  InboxPageHeader,
  InboxTotalsOrStarter,
  MailDropSourcesSection,
  RoutingQueueSection,
  SourceLanesSection,
  UnifiedRunsSection,
  VaultTargetsSection,
  WatchedFoldersSection,
} from "./inbox.sections";

export default function InboxPage() {
  const {
    data,
    folders,
    emailSources,
    sourceLanes,
    vaultTargets,
    discoveredVaults,
    routingQueue,
    latestUnifiedRuns,
    totals,
    loading,
    error,
    runStatus,
    actionState,
    notice,
    addFolder,
    addEmailSource,
    refresh,
    runFolderAction,
    runEmailAction,
    registerVault,
    discoverVaults,
    routePacket,
    consumePacket,
  } = useBrainInbox();
  const [folderName, setFolderName] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [emailDisplayName, setEmailDisplayName] = useState("");
  const [emailPath, setEmailPath] = useState("");
  const hasWatchedFolders = folders.length > 0;
  const hasInboxActivity = totals.newFiles + totals.documents + totals.trash + totals.failed > 0;
  const isAddingEmail = actionState?.folderId === "email:new";
  const isInitialLoading = loading && !error;
  const showWatchedFolders = isInitialLoading || Boolean(error) || hasWatchedFolders;

  const selectPreset = (preset: { name: string; path: string }) => {
    setFolderName(preset.name);
    setFolderPath(preset.path);
  };

  const handleAddFolder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const path = folderPath.trim();
    if (!path) {
      return;
    }
    const added = await addFolder(path, folderName);
    if (added) {
      setFolderName("");
      setFolderPath("");
    }
  };

  const handleAddEmailSource = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const displayName = emailDisplayName.trim();
    const path = emailPath.trim();
    if (!displayName || !path) {
      return;
    }
    const added = await addEmailSource({
      displayName,
      path,
    });
    if (added) {
      setEmailDisplayName("");
      setEmailPath("");
    }
  };

  return (
    <div className="space-y-6">
      <InboxPageHeader runStatus={runStatus} onRefresh={refresh} />

      <InboxHealthStrip
        sourceCount={sourceLanes.length}
        targetCount={vaultTargets.length}
        candidateCount={discoveredVaults.length}
        queuedCount={routingQueue.length}
      />

      <SourceLanesSection sourceLanes={sourceLanes} />
      <VaultTargetsSection
        discoveredVaults={discoveredVaults}
        onDiscover={discoverVaults}
        onRegister={registerVault}
        vaultTargets={vaultTargets}
      />
      <RoutingQueueSection
        onConsume={consumePacket}
        onRoute={routePacket}
        routingQueue={routingQueue}
      />
      <UnifiedRunsSection runs={latestUnifiedRuns} />
      <InboxTotalsOrStarter
        hasInboxActivity={hasInboxActivity}
        hasWatchedFolders={hasWatchedFolders}
        onSelectPreset={selectPreset}
        totals={totals}
      />
      <AddFolderSection
        actionState={actionState}
        folderName={folderName}
        folderPath={folderPath}
        onFolderNameChange={setFolderName}
        onFolderPathChange={setFolderPath}
        onSubmit={handleAddFolder}
      />
      <AddMailDropSection
        displayName={emailDisplayName}
        isAddingEmail={isAddingEmail}
        onDisplayNameChange={setEmailDisplayName}
        onPathChange={setEmailPath}
        onSubmit={handleAddEmailSource}
        path={emailPath}
      />
      <InboxNotice notice={notice} />
      {isInitialLoading && <div className="text-sm text-[var(--text-muted)]">Loading inbox folders…</div>}
      {error && <div className="text-sm text-[var(--accent-danger)]">Brain Inbox could not be loaded: {error}</div>}
      <MailDropSourcesSection
        actionState={actionState}
        emailSources={emailSources}
        onAction={runEmailAction}
      />
      <WatchedFoldersSection
        actionState={actionState}
        error={error}
        folders={folders}
        isInitialLoading={isInitialLoading}
        onAction={runFolderAction}
        onSelectPreset={selectPreset}
        show={showWatchedFolders}
      />

      <LatestRunList runs={data?.success === false ? [] : data?.latest_runs ?? []} />
    </div>
  );
}
