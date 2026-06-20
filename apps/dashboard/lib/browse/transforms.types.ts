export type SkillOwnership = "augur" | "external" | "adopted" | "user";

export type SkillRecord = {
  name?: string;
  display_name?: string;
  description?: string;
  hub?: string | null;
  master?: string;
  source?: string;
  source_root?: string;
  sourceRoot?: string;
  plugin?: string;
  ownership?: string;
  upstream?: Record<string, unknown>;
  category?: string;
  group?: string;
  release?: string;
  skill_type?: string;
  skillClients?: string[] | string;
  skill_clients?: string[] | string;
  clientSources?: string[] | string;
  client_sources?: string[] | string;
  tags?: string[];
  hasDocs?: string | boolean;
  has_docs?: string | boolean;
};
