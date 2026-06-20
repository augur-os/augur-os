"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { push, refresh } = useRouter();
  const queryClient = useQueryClient();

  const { mutateAsync: login, isPending: loading } = useMutation({
    mutationFn: async (body: { username: string; password: string }) => {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Login failed (${res.status})`);
      }
      return res.json();
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      push("/");
      refresh();
    },
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    try {
      await login({ username, password });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Network error — is the server running?",
      );
    }
  }

  return (
    <main className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans px-4">
      <GlassCard color="purple" showHoverGlow={false} className="w-full max-w-[360px]">
        <form onSubmit={handleSubmit} className="p-5 sm:p-6" aria-busy={loading}>
          <h1 className="text-2xl font-semibold mb-2">Augur</h1>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Sign in to continue
          </p>

          {error && (
            <div
              role="alert"
              className="px-3 py-2 mb-4 rounded-lg bg-[var(--accent-danger)]/10 border border-[var(--accent-danger)]/30 text-[var(--accent-danger)] text-[13px]"
            >
              {error}
            </div>
          )}

          <label htmlFor="login-username" className="block mb-4">
            <span className="block text-[13px] mb-1 text-[var(--text-secondary)]">
              Username
            </span>
            <Input
              id="login-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
              disabled={loading}
              className="h-11 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </label>

          <label htmlFor="login-password" className="block mb-6">
            <span className="block text-[13px] mb-1 text-[var(--text-secondary)]">
              Password
            </span>
            <Input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              disabled={loading}
              className="h-11 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </label>

          <Button
            type="submit"
            variant="solid"
            width="full"
            disabled={loading}
            isLoading={loading}
            loadingText="Signing in..."
            aria-busy={loading}
            className="h-11"
          >
            Sign in
          </Button>
        </form>
      </GlassCard>
    </main>
  );
}
