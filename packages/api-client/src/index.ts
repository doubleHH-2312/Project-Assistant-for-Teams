export type WorkStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "BLOCKED"
  | "READY_FOR_REVIEW"
  | "DONE";

export interface DailyReportInput {
  projectId: string;
  workItemId: string;
  reportDate: string;
  status: WorkStatus;
  workSummary: string;
  blocker: string | null;
  nextAction: string;
}

export interface DailyReport extends DailyReportInput {
  id: string;
  userId: string;
  effectiveBlocker: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface TeamOverview {
  reportingDate: string;
  coverage: { submitted: number; expected: number; percentage: number };
  missingReporters: Array<{ id: string; name: string }>;
  statusCounts: Record<string, number>;
  blockers: Array<{
    reportId: string;
    userId: string;
    workItemId: string;
    effectiveBlocker: string;
    ageDays: number;
    nextAction: string;
  }>;
}

export interface WeeklyReport {
  id: string;
  scope: "MEMBER" | "TEAM";
  subjectUserId: string | null;
  teamId: string;
  weekStart: string;
  weekEnd: string;
  contentJson: Record<string, string[]>;
  missingContributors: string[];
  inputRecordIds: string[];
  generationSource: string;
  generationMetadata: Record<string, unknown>;
  status: "DRAFT" | "GENERATED" | "EDITED" | "CONFIRMED";
  templateId: string;
  templateVersion: number;
  supersedesId: string | null;
  confirmedAt: string | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public correlationId?: string,
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

  createDailyReport(input: DailyReportInput): Promise<DailyReport> {
    return this.request("/daily-reports", { method: "POST", body: JSON.stringify(input) });
  }

  listMyDailyReports(): Promise<DailyReport[]> {
    return this.request("/daily-reports/me");
  }

  getOverview(teamId: string, reportingDate: string): Promise<TeamOverview> {
    const query = new URLSearchParams({ reportingDate });
    return this.request(`/teams/${teamId}/overview?${query}`);
  }

  generateWeekly(scope: "MEMBER" | "TEAM", weekStart: string): Promise<WeeklyReport> {
    return this.request("/weekly-reports/generate", {
      method: "POST",
      body: JSON.stringify({ scope, weekStart }),
    });
  }

  confirmWeekly(reportId: string): Promise<WeeklyReport> {
    return this.request(`/weekly-reports/${reportId}/confirm`, { method: "POST" });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    else headers.set("X-Dev-User-ID", this.userId);
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.code ?? "REQUEST_FAILED",
        error.message ?? "Request failed. Try again.",
        error.correlationId,
      );
    }
    return response.json() as Promise<T>;
  }
}
