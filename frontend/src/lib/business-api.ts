import { queryOptions } from "@tanstack/react-query";
import { api } from "./api-client";
import { shouldPoll } from "./status";
import {
  projectSchema,
  capabilitiesSchema,
  connectionSchema,
  modelListSchema,
  agentRunSchema,
  itemSchema,
  runSchema,
  eventSchema,
  artifactSchema,
  approvalSchema,
  dashboardSchema,
  pageSchema,
} from "@/types/contracts";
import type { ApprovalDecision } from "@/types/contracts";

const root = "/api/v1";
export const capabilitiesOptions = queryOptions({
  queryKey: ["capabilities"],
  queryFn: ({ signal }) =>
    api.request(`${root}/capabilities`, capabilitiesSchema.parse, { signal }),
  refetchInterval: 5000,
});
export const connectionsOptions = (offset = 0) =>
  queryOptions({
    queryKey: ["ai-connections", offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/ai-connections?limit=100&offset=${offset}`,
        pageSchema(connectionSchema).parse,
        { signal },
      ),
  });
export const agentRunsOptions = (id: string, offset: number, active: boolean) =>
  queryOptions({
    queryKey: ["agent-runs", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/workflow-runs/${id}/agent-runs?limit=25&offset=${offset}`,
        pageSchema(agentRunSchema).parse,
        { signal },
      ),
    refetchInterval: active ? 3000 : false,
  });
export const artifactOptions = (runId: string, artifactId: string) =>
  queryOptions({
    queryKey: ["artifact", runId, artifactId],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/workflow-runs/${runId}/artifacts/${artifactId}`,
        artifactSchema.parse,
        { signal },
      ),
  });
export const projectOptions = (id: string) =>
  queryOptions({
    queryKey: ["project", id],
    queryFn: ({ signal }) =>
      api.request(`${root}/projects/${id}`, projectSchema.parse, { signal }),
  });
export const projectsOptions = (offset: number) =>
  queryOptions({
    queryKey: ["projects", offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/projects?limit=25&offset=${offset}`,
        pageSchema(projectSchema).parse,
        { signal },
      ),
  });
export const itemsOptions = (id: string, offset: number) =>
  queryOptions({
    queryKey: ["items", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/projects/${id}/work-items?limit=25&offset=${offset}`,
        pageSchema(itemSchema).parse,
        { signal },
      ),
  });
export const itemOptions = (id: string) =>
  queryOptions({
    queryKey: ["item", id],
    queryFn: ({ signal }) =>
      api.request(`${root}/work-items/${id}`, itemSchema.parse, { signal }),
  });
export const runsOptions = (id: string, offset: number) =>
  queryOptions({
    queryKey: ["runs", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/work-items/${id}/workflow-runs?limit=25&offset=${offset}`,
        pageSchema(runSchema).parse,
        { signal },
      ),
  });
export const runOptions = (id: string) =>
  queryOptions({
    queryKey: ["run", id],
    queryFn: ({ signal }) =>
      api.request(`${root}/workflow-runs/${id}`, runSchema.parse, { signal }),
    refetchInterval: (query) =>
      query.state.data && shouldPoll(query.state.data.status) ? 3000 : false,
  });
export const eventsOptions = (id: string, offset: number, active: boolean) =>
  queryOptions({
    queryKey: ["events", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/workflow-runs/${id}/events?limit=25&offset=${offset}`,
        pageSchema(eventSchema).parse,
        { signal },
      ),
    refetchInterval: active ? 3000 : false,
  });
export const artifactsOptions = (id: string, offset: number) =>
  queryOptions({
    queryKey: ["artifacts", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/workflow-runs/${id}/artifacts?limit=25&offset=${offset}`,
        pageSchema(artifactSchema).parse,
        { signal },
      ),
  });
export const approvalsOptions = (id: string, offset: number) =>
  queryOptions({
    queryKey: ["approvals", id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `${root}/workflow-runs/${id}/approvals?limit=25&offset=${offset}`,
        pageSchema(approvalSchema).parse,
        { signal },
      ),
  });
export const dashboardOptions = queryOptions({
  queryKey: ["dashboard"],
  queryFn: ({ signal }) =>
    api.request(`${root}/dashboard`, dashboardSchema.parse, { signal }),
  refetchInterval: 10000,
});
export const commands = {
  discoverModels: (provider: string, api_key: string) =>
    api.request(`${root}/ai-connections/models`, modelListSchema.parse, {
      method: "POST",
      body: JSON.stringify({ provider, api_key }),
    }),
  createConnection: (body: {
    name: string;
    provider: string;
    api_key: string;
    model: string;
  }) =>
    api.request(`${root}/ai-connections`, connectionSchema.parse, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  disableConnection: (id: string) =>
    api.request(
      `${root}/ai-connections/${id}/disable`,
      connectionSchema.parse,
      { method: "POST" },
    ),
  createProject: (body: { name: string; description: string }) =>
    api.request(`${root}/projects`, projectSchema.parse, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  archiveProject: (id: string, status: "active" | "archived") =>
    api.request(`${root}/projects/${id}`, projectSchema.parse, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  createItem: (
    id: string,
    body: {
      title: string;
      description: string;
      acceptance_criteria: string;
      priority: string;
    },
  ) =>
    api.request(`${root}/projects/${id}/work-items`, itemSchema.parse, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  start: (
    id: string,
    key: string,
    mode: "mock" | "ba_live" | "static_site" = "mock",
    connection_id?: string,
  ) =>
    api.request(`${root}/work-items/${id}/workflow-runs`, runSchema.parse, {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify({
        mode,
        connection_id: mode !== "mock" ? connection_id : undefined,
      }),
    }),
  approve: (id: string, body: ApprovalDecision) =>
    api.request(`${root}/workflow-runs/${id}/approvals`, runSchema.parse, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancel: (id: string) =>
    api.request(`${root}/workflow-runs/${id}/cancel`, runSchema.parse, {
      method: "POST",
      body: JSON.stringify({ reason: "Cancelled by PM from dashboard" }),
    }),
  retry: (id: string, connection_id?: string) =>
    api.request(`${root}/workflow-runs/${id}/retry`, runSchema.parse, {
      method: "POST",
      body: JSON.stringify({ connection_id }),
    }),
};
