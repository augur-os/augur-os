import { redirect } from "next/navigation";
import { RETIRED_VIEW_MODES } from "@/lib/browse/types";
import { BrowsePageClient } from "./BrowsePageClient";

export const dynamic = "force-dynamic";

interface BrowsePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) return value[0] ?? null;
  return value ?? null;
}

function toSearchParams(
  values: Record<string, string | string[] | undefined>,
): URLSearchParams {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((entry) => params.append(key, entry));
      return;
    }
    if (value !== undefined) {
      params.set(key, value);
    }
  });
  return params;
}

export default async function BrowsePage({ searchParams }: BrowsePageProps) {
  const paramsRecord = await searchParams;
  const rawUrlCategory = firstParam(paramsRecord.category);
  const rawUrlView = firstParam(paramsRecord.view);
  const rawUrlMode = rawUrlCategory || rawUrlView;

  if (rawUrlCategory === "scheduled-executions") {
    const params = toSearchParams(paramsRecord);
    params.set("category", "background-routines");
    redirect(`/browse?${params.toString()}`);
  }

  if (rawUrlMode) {
    const retired = RETIRED_VIEW_MODES[rawUrlMode];
    if (retired) {
      const params = toSearchParams(paramsRecord);
      params.delete("category");
      params.set("view", retired.view);
      if (retired.type) {
        params.set("type", retired.type);
      } else {
        params.delete("type");
      }
      redirect(`/browse?${params.toString()}`);
    }
  }

  return <BrowsePageClient />;
}
