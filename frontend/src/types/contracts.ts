import { z } from "zod";
export const capabilitiesSchema = z.object({
  ba_live_available: z.boolean(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  key_storage_available: z.boolean(),
});
export const connectionSchema = z.object({
  id: z.string(),
  name: z.string(),
  provider: z.string(),
  model: z.string(),
  enabled: z.boolean(),
  created_at: z.string(),
});
export const modelListSchema = z.object({ models: z.array(z.string()) });
export const specificationSchema = z.object({
  title: z.string(),
  summary: z.string(),
  user_stories: z.array(
    z.object({
      id: z.string(),
      role: z.string(),
      goal: z.string(),
      benefit: z.string(),
    }),
  ),
  acceptance_criteria: z.array(
    z.object({
      id: z.string(),
      story_id: z.string(),
      given: z.string(),
      when: z.string(),
      then: z.string(),
    }),
  ),
  edge_cases: z.array(z.string()),
  non_functional_requirements: z.array(z.string()),
  open_questions: z.array(z.string()),
  assumptions: z.array(z.string()),
});
export const agentRunSchema = z.object({
  id: z.string(),
  role: z.string(),
  status: z.string(),
  model: z.string(),
  provider: z.string(),
  revision: z.number(),
  attempt: z.number(),
  input_tokens: z.number().nullable(),
  output_tokens: z.number().nullable(),
  duration_ms: z.number().nullable(),
  error_code: z.string().nullable(),
  connection_id: z.string().nullable(),
});
const identity = { id: z.string(), created_at: z.string() };
export const projectSchema = z.object({
  ...identity,
  name: z.string(),
  description: z.string(),
  owner: z.string(),
  status: z.enum(["active", "archived"]),
  updated_at: z.string(),
});
export const itemSchema = z.object({
  ...identity,
  project_id: z.string(),
  title: z.string(),
  description: z.string(),
  acceptance_criteria: z.string(),
  priority: z.string(),
  status: z.string(),
  updated_at: z.string(),
});
export const runSchema = z.object({
  ...identity,
  work_item_id: z.string(),
  status: z.string(),
  current_step: z.string(),
  attempt: z.number(),
  revision: z.number(),
  repair_count: z.number(),
  retryable: z.boolean(),
  failed_step: z.string().nullable(),
  gate_id: z.string().nullable(),
  gate_artifact_id: z.string().nullable(),
  started_at: z.string().nullable(),
  ended_at: z.string().nullable(),
  failure_reason: z.string().nullable(),
  cancellation_reason: z.string().nullable(),
  snapshot: z.object({ mode: z.string(), version: z.string() }).passthrough(),
});
export const eventSchema = z.object({
  id: z.number(),
  run_id: z.string(),
  event_type: z.string(),
  payload: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});
export const artifactSchema = z.object({
  ...identity,
  run_id: z.string(),
  gate_id: z.string(),
  kind: z.string(),
  revision: z.number(),
  attempt: z.number(),
  content: z.record(z.string(), z.unknown()),
});
export const approvalSchema = z.object({
  ...identity,
  run_id: z.string(),
  step: z.string(),
  attempt: z.number(),
  revision: z.number(),
  decision: z.string(),
  reviewer: z.string(),
  comment: z.string().nullable(),
  gate_id: z.string().nullable(),
  artifact_id: z.string().nullable(),
  return_to: z.string().nullable(),
});
export const dashboardSchema = z.object({
  counts: z.record(z.string(), z.number()),
  recent_runs: z.array(runSchema),
  waiting_runs: z.array(runSchema),
  recent_events: z.array(eventSchema),
});
export const pageSchema = <T extends z.ZodType>(schema: T) =>
  z.object({ items: z.array(schema), limit: z.number(), offset: z.number() });
export type Project = z.infer<typeof projectSchema>;
export type WorkItem = z.infer<typeof itemSchema>;
export type Run = z.infer<typeof runSchema>;
export type Artifact = z.infer<typeof artifactSchema>;
export type ApprovalDecision = {
  step: string;
  attempt: number;
  gate_id: string | null;
  artifact_id: string | null;
  decision: "approve" | "reject";
  comment?: string;
  return_to?: "ba_in_progress" | "plan_in_progress";
};
