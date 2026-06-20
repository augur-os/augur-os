import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface CreateSkillRequest {
  name: string;
  description: string;
  layer?: "factory" | "horizontal" | "vertical";
  patterns: string[];
  ideTargets?: string[];
}

const KEBAB_CASE_PATTERN = /^[a-z][a-z0-9-]*$/;

function validateSkillName(name: string): string | null {
  if (!name || !name.trim()) {
    return "Skill name is required";
  }
  if (!KEBAB_CASE_PATTERN.test(name)) {
    return "Skill name must be kebab-case (lowercase letters, numbers, hyphens only)";
  }
  return null;
}

function validateCreateRequest(body: CreateSkillRequest): string | null {
  const nameError = validateSkillName(body.name);
  if (nameError) {
    return nameError;
  }

  if (!body.patterns || body.patterns.length === 0) {
    return "At least one pattern is required";
  }

  return null;
}

function buildGenerateUrl(requestUrl: string): string {
  return requestUrl.replace("/create", "/generate");
}

function toUnifiedErrorMessage(unifiedData: any): {
  error: string;
  message?: string;
} {
  return {
    error: unifiedData?.errors?.[0] || "Failed to create skill",
    message: unifiedData?.errors?.join(", ") || unifiedData?.error,
  };
}

export async function POST(req: Request): Promise<NextResponse> {
  try {
    const body = (await req.json()) as CreateSkillRequest;
    const validationError = validateCreateRequest(body);
    if (validationError) {
      return NextResponse.json({ error: validationError }, { status: 400 });
    }

    const unifiedResponse = await fetch(buildGenerateUrl(req.url), {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "create",
        name: body.name,
        description: body.description,
        patterns: body.patterns,
        layer: body.layer || "vertical",
      }),
    });

    const unifiedData = await unifiedResponse.json();

    if (!unifiedResponse.ok || !unifiedData.success) {
      return NextResponse.json(toUnifiedErrorMessage(unifiedData), {
        status: unifiedResponse.status || 500,
      });
    }

    // Transform to backward-compatible format
    return NextResponse.json({
      success: true,
      message: `Skill "${body.name}" created successfully in ${unifiedData.skill.layer} layer`,
      path: unifiedData.skill.path,
      layer: unifiedData.skill.layer,
      output: unifiedData.generated,
      ideTargets: body.ideTargets || [],
    });
  } catch (error) {
    console.error("Failed to create skill:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: "Failed to create skill",
        message: errorMessage,
      },
      { status: 500 },
    );
  }
}
