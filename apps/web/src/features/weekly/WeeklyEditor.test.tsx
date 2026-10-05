import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProjectAssistantClient, type WeeklyReport } from "@project-assistant/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WeeklyEditor } from "./WeeklyEditor";

const draft: WeeklyReport = {
  id: "weekly-1",
  scope: "MEMBER",
  subjectUserId: "user-1",
  teamId: "team-1",
  teamIds: [],
  weekStart: "2026-09-28",
  weekEnd: "2026-10-02",
  contentJson: { projects: [{ name: "Project A", tasks: ["OPS-142"] }] },
  missingContributors: [],
  inputRecordIds: ["daily-1"],
  generationSource: "MOCK",
  generationMetadata: {},
  status: "DRAFT",
  templateId: "template-1",
  templateVersion: 1,
  supersedesId: null,
  confirmedAt: null,
};

function renderEditor(report = draft) {
  const client = new ProjectAssistantClient("/api/v1", "user-1");
  const onChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WeeklyEditor client={client} report={report} teamId="team-1" onChange={onChange} />
    </QueryClientProvider>,
  );
  return { client, onChange };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("WeeklyEditor", () => {
  it("saves edited evidence and confirms separately", async () => {
    const update = vi.spyOn(ProjectAssistantClient.prototype, "updateWeekly").mockResolvedValue(draft);
    const confirm = vi.spyOn(ProjectAssistantClient.prototype, "confirmWeekly").mockResolvedValue({ ...draft, status: "CONFIRMED", confirmedAt: "2026-10-05T09:00:00Z" });
    renderEditor();
    fireEvent.change(screen.getByLabelText("Report content"), { target: { value: JSON.stringify({ projects: [] }) } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith("weekly-1", "team-1", { projects: [] }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm report" }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("weekly-1", "team-1"));
  });

  it("requires explicit publication approval and supports immutable revision", async () => {
    const confirmed = { ...draft, status: "CONFIRMED", confirmedAt: "2026-10-05T09:00:00Z" } satisfies WeeklyReport;
    const revise = vi.spyOn(ProjectAssistantClient.prototype, "createWeeklyRevision").mockResolvedValue({ ...draft, supersedesId: draft.id });
    const publish = vi.spyOn(ProjectAssistantClient.prototype, "publishWeekly").mockResolvedValue({ id: "publication-1", weeklyReportId: draft.id, conversationId: "conversation-1", actorId: "user-1", idempotencyKey: "test-key", publishedAt: "2026-10-05T10:00:00Z" });
    renderEditor(confirmed);
    fireEvent.click(screen.getByRole("button", { name: "Create revision" }));
    await waitFor(() => expect(revise).toHaveBeenCalled());
    const publishButton = screen.getByRole("button", { name: "Publish confirmed report" });
    expect(publishButton).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Captured Teams conversation ID"), { target: { value: "conversation-1" } });
    fireEvent.click(screen.getByRole("checkbox"));
    expect(publishButton).toBeEnabled();
    fireEvent.click(publishButton);
    await waitFor(() => expect(publish).toHaveBeenCalledWith("weekly-1", "conversation-1"));
  });
});
