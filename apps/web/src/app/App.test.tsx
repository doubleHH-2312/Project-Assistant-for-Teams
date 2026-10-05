import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  ProjectAssistantClient,
  type DailyReport,
  type Permission,
  type SessionSnapshot,
} from "@project-assistant/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const allPermissions: Permission[] = [
  "SUBMIT_OWN_DAILY",
  "VIEW_OWN_HISTORY",
  "GENERATE_OWN_WEEKLY",
  "VIEW_TEAM_DAILY_SUMMARY",
  "GENERATE_TEAM_WEEKLY",
  "GENERATE_MULTI_TEAM_WEEKLY",
  "MANAGE_TEAMS_BINDING",
];

function session(role: "MEMBER" | "TECH_LEAD" | "PM"): SessionSnapshot {
  const permissions =
    role === "MEMBER"
      ? allPermissions.slice(0, 3)
      : role === "TECH_LEAD"
        ? allPermissions.slice(0, 6)
        : allPermissions;
  return {
    id: `user-${role.toLowerCase()}`,
    name: role === "MEMBER" ? "An Nguyen" : role === "TECH_LEAD" ? "Binh Tran" : "Chi Le",
    email: `${role.toLowerCase()}@example.test`,
    tenantId: "tenant-1",
    teams: [
      {
        teamId: "team-ops",
        teamName: "Operations",
        timezone: "Asia/Ho_Chi_Minh",
        role,
        permissions,
      },
      {
        teamId: "team-platform",
        teamName: "Platform",
        timezone: "Asia/Ho_Chi_Minh",
        role,
        permissions,
      },
    ],
  };
}

function renderApp() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("role-aware application shell", () => {
  it("shows only member navigation returned by the server", async () => {
    vi.spyOn(ProjectAssistantClient.prototype, "getSession").mockResolvedValue(
      session("MEMBER"),
    );
    vi.spyOn(ProjectAssistantClient.prototype, "listDailyOptions").mockResolvedValue({
      projects: [],
      workItems: [],
    });

    renderApp();

    expect(await screen.findByRole("heading", { name: "Project Assistant" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Daily update" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "History" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "My weekly" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Team overview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Multi-team weekly" })).not.toBeInTheDocument();
  });

  it("adds lead actions without granting PM-only settings", async () => {
    vi.spyOn(ProjectAssistantClient.prototype, "getSession").mockResolvedValue(
      session("TECH_LEAD"),
    );
    vi.spyOn(ProjectAssistantClient.prototype, "listDailyOptions").mockResolvedValue({
      projects: [],
      workItems: [],
    });

    renderApp();

    expect(await screen.findByRole("button", { name: "Team overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Team weekly" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Multi-team weekly" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Team settings" })).not.toBeInTheDocument();
  });

  it("lets a PM select multiple Teams for a cross-team report", async () => {
    vi.spyOn(ProjectAssistantClient.prototype, "getSession").mockResolvedValue(session("PM"));
    vi.spyOn(ProjectAssistantClient.prototype, "listDailyOptions").mockResolvedValue({
      projects: [],
      workItems: [],
    });

    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: "Multi-team weekly" }));

    expect(screen.getByRole("checkbox", { name: "Operations" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Platform" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Team settings" })).toBeInTheDocument();
  });

  it("renders exact report dates in Daily history", async () => {
    vi.spyOn(ProjectAssistantClient.prototype, "getSession").mockResolvedValue(
      session("MEMBER"),
    );
    vi.spyOn(ProjectAssistantClient.prototype, "listDailyOptions").mockResolvedValue({
      projects: [],
      workItems: [],
    });
    vi.spyOn(ProjectAssistantClient.prototype, "listDailyHistory").mockResolvedValue([
      {
        id: "daily-1",
        teamId: "team-ops",
        userId: "user-member",
        projectId: "project-1",
        workItemId: "OPS-142",
        reportDate: "2026-10-04",
        status: "BLOCKED",
        workSummary: "Waiting for access",
        blocker: null,
        effectiveBlocker: "Waiting for access",
        nextAction: "Escalate",
        source: "WEB",
        submittedAt: "2026-10-04T09:00:00Z",
        lastEditedAt: null,
        createdAt: "2026-10-04T09:00:00Z",
        updatedAt: "2026-10-04T09:00:00Z",
      } satisfies DailyReport,
    ]);

    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: "History" }));

    expect(await screen.findByText("2026-10-04")).toBeInTheDocument();
    expect(screen.getByText("Waiting for access")).toBeInTheDocument();
  });

  it("shows a retry action when session data becomes stale or unavailable", async () => {
    const getSession = vi
      .spyOn(ProjectAssistantClient.prototype, "getSession")
      .mockRejectedValueOnce(new Error("Session unavailable"))
      .mockResolvedValueOnce(session("MEMBER"));

    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    await waitFor(() => expect(getSession).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("button", { name: "Daily update" })).toBeInTheDocument();
  });
});
