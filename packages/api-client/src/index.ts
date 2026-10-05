import type { components } from "./schema";

export type Permission = components["schemas"]["Permission"];
export type TeamRole = components["schemas"]["TeamRole"];
export type TeamAccess = components["schemas"]["TeamAccess"];
export type SessionSnapshot = components["schemas"]["SessionSnapshot"];
export type WorkStatus = components["schemas"]["WorkStatus"];
export type DailyReportInput = components["schemas"]["DailyReportCreate"];
export type DailyReportUpdate = components["schemas"]["DailyReportUpdate"];
export type DailyReport = components["schemas"]["DailyReportRead"];
export type TeamOverview = components["schemas"]["TeamOverview"];
export type ReportScope = components["schemas"]["ReportScope"];
export type WeeklyGenerateRequest = components["schemas"]["WeeklyGenerateRequest"];
export type WeeklyReport = components["schemas"]["WeeklyReportRead"];
export type Publication = components["schemas"]["PublicationRead"];

export interface DailyOptions {
  projects: ReadonlyArray<{ id: string; name: string }>;
  workItems: ReadonlyArray<{
    id: string;
    projectId: string;
    code: string;
    title: string;
  }>;
}

export interface DailyHistoryFilters {
  teamId: string;
  dateFrom?: string;
  dateTo?: string;
  projectId?: string;
  status?: WorkStatus;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
  correlationId?: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
    public readonly correlationId?: string,
  ) {
    super(message);
  }
}

export class ProjectAssistantClient {
  constructor(
    private readonly baseUrl: string,
    private readonly userId: string,
    private readonly token?: string,
  ) {}

  getSession(): Promise<SessionSnapshot> {
    return this.request("/me");
  }

  listTeams(): Promise<readonly TeamAccess[]> {
    return this.request("/teams");
  }

  listDailyOptions(teamId: string): Promise<DailyOptions> {
    return this.request(`/daily-reports/options?${queryString({ teamId })}`);
  }

  createDailyReport(
    input: DailyReportInput,
    idempotencyKey = createIdempotencyKey("daily"),
  ): Promise<DailyReport> {
    return this.request("/daily-reports", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    });
  }

  updateDailyReport(
    reportId: string,
    teamId: string,
    input: DailyReportUpdate,
    idempotencyKey = createIdempotencyKey("daily-edit"),
  ): Promise<DailyReport> {
    return this.request(
      `/daily-reports/${encodeURIComponent(reportId)}?${queryString({ teamId })}`,
      {
        method: "PUT",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(input),
      },
    );
  }

  listDailyHistory(filters: DailyHistoryFilters): Promise<readonly DailyReport[]> {
    return this.request(`/daily-reports/history?${queryString({
      teamId: filters.teamId,
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
      projectId: filters.projectId,
      status: filters.status,
    })}`);
  }

  getOverview(teamId: string, reportingDate: string): Promise<TeamOverview> {
    return this.request(
      `/teams/${encodeURIComponent(teamId)}/overview?${queryString({ reportingDate })}`,
    );
  }

  generateWeekly(
    input: WeeklyGenerateRequest,
    idempotencyKey = createIdempotencyKey("weekly"),
  ): Promise<WeeklyReport> {
    return this.request("/weekly-reports/generate", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    });
  }

  getWeekly(reportId: string, teamId?: string): Promise<WeeklyReport> {
    return this.request(
      `/weekly-reports/${encodeURIComponent(reportId)}?${queryString({ teamId })}`,
    );
  }

  updateWeekly(
    reportId: string,
    teamId: string | undefined,
    contentJson: Record<string, unknown>,
    idempotencyKey = createIdempotencyKey("weekly-edit"),
  ): Promise<WeeklyReport> {
    return this.request(
      `/weekly-reports/${encodeURIComponent(reportId)}?${queryString({ teamId })}`,
      {
        method: "PUT",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ contentJson }),
      },
    );
  }

  confirmWeekly(
    reportId: string,
    teamId?: string,
    idempotencyKey = createIdempotencyKey("weekly-confirm"),
  ): Promise<WeeklyReport> {
    return this.request(
      `/weekly-reports/${encodeURIComponent(reportId)}/confirm?${queryString({ teamId })}`,
      { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    );
  }

  createWeeklyRevision(
    reportId: string,
    teamId?: string,
    idempotencyKey = createIdempotencyKey("weekly-revision"),
  ): Promise<WeeklyReport> {
    return this.request(
      `/weekly-reports/${encodeURIComponent(reportId)}/revisions?${queryString({ teamId })}`,
      { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    );
  }

  publishWeekly(
    reportId: string,
    conversationId: string,
    idempotencyKey = createIdempotencyKey("weekly-publish"),
  ): Promise<Publication> {
    return this.request(`/weekly-reports/${encodeURIComponent(reportId)}/publish`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ conversationId }),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    else headers.set("X-Dev-User-ID", this.userId);
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({}))) as ApiErrorBody;
      throw new ApiError(
        response.status,
        error.code ?? "REQUEST_FAILED",
        error.message ?? "Request failed. Try again.",
        error.details,
        error.correlationId,
      );
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}

function queryString(values: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value) query.set(key, value);
  }
  return query.toString();
}

function createIdempotencyKey(action: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `web:${action}:${suffix}`;
}
