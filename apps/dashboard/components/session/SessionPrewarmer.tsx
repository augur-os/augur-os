"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";

interface SessionPrewarmPayload {
  airplaneMode: boolean;
  airplaneLocalModel: string | null;
  currentPage?: string;
  themeMode: "light" | "dark";
}

export default function SessionPrewarmer(): null {
  const queryClient = useQueryClient();
  const lastAirplaneRoute = useRef<{
    enabled: boolean;
    model: string | null;
  } | null>(null);
  const pathname = usePathname();
  const {
    airplaneMode,
    airplaneModeReady,
    airplaneBackendReady,
    airplaneLocalModel,
  } = useAirplaneModeStore();
  const { mutate: prewarmSession } = useMutation({
    mutationFn: async (payload: SessionPrewarmPayload) => {
      await fetch("/api/session/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (_data, payload) => {
      queryClient.setQueryData(
        [
          "session-prewarm",
          payload.airplaneMode,
          payload.airplaneLocalModel,
          payload.currentPage,
          payload.themeMode,
        ],
        true,
      );
    },
  });

  useEffect(() => {
    if (!airplaneModeReady) return;
    if (airplaneMode && !airplaneBackendReady) return;
    const route = {
      enabled: airplaneMode,
      model: airplaneMode ? airplaneLocalModel : null,
    };
    if (
      lastAirplaneRoute.current?.enabled === route.enabled &&
      lastAirplaneRoute.current?.model === route.model
    ) {
      return;
    }
    lastAirplaneRoute.current = route;

    const mode = document.documentElement.getAttribute("data-mode");
    prewarmSession({
      airplaneMode,
      airplaneLocalModel: route.model,
      currentPage: pathname || undefined,
      themeMode: mode === "light" ? "light" : "dark",
    });
  }, [
    airplaneMode,
    airplaneModeReady,
    airplaneBackendReady,
    airplaneLocalModel,
    pathname,
    prewarmSession,
  ]);

  return null;
}
