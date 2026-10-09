import { Button, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DailyReportInput, WorkStatus } from "@project-assistant/api-client";
import { useMemo, useState, type FormEvent } from "react";
import { useSession } from "../../app/session-context";
import { todayInTimeZone } from "../../app/team-calendar";
import { AsyncState } from "../../components/AsyncState";

export function DailyPage() {
  const { client, team, teamId } = useSession();
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState("");
  const options = useQuery({
    queryKey: ["daily-options", teamId],
    queryFn: () => client.listDailyOptions(teamId),
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: (input: DailyReportInput) => client.createDailyReport(input),
    onSuccess: (report) => {
      setSaved(`Saved ${report.workItemId} for ${report.reportDate}.`);
      void queryClient.invalidateQueries({ queryKey: ["daily-history", teamId] });
      void queryClient.invalidateQueries({ queryKey: ["overview", teamId] });
    },
  });
  const workItems = useMemo(() => options.data?.workItems ?? [], [options.data]);

  if (options.isPending) return <AsyncState kind="loading" title="Loading daily form" />;
  if (options.isError) {
    return (
      <AsyncState
        kind="error"
        title="Daily form is unavailable"
        detail={options.error.message}
        retry={() => void options.refetch()}
      />
    );
  }
  if (!options.data || options.data.projects.length === 0 || workItems.length === 0) {
    return (
      <AsyncState
        title="No active work is assigned"
        detail="Ask a Team lead or PM to assign an active project and work item."
      />
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved("");
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      teamId,
      projectId: String(form.get("projectId")),
      workItemId: String(form.get("workItemId")),
      reportDate: String(form.get("reportDate")),
      status: String(form.get("status")) as WorkStatus,
      workSummary: String(form.get("workSummary")),
      blocker: String(form.get("blocker") || "") || null,
      nextAction: String(form.get("nextAction")),
    });
  }

  return (
    <section className="panel" aria-labelledby="daily-title">
      <PageHeading eyebrow="MEMBER WORKFLOW" title="Record a daily update" detail="The system records the report date and submit time automatically." />
      <form className="report-form" onSubmit={submit}>
        <label className="field">
          <span>Project</span>
          <select name="projectId" required>
            {options.data.projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Work item</span>
          <select name="workItemId" required>
            {workItems.map((item) => <option key={item.id} value={item.id}>{item.code}: {item.title}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Report date</span>
          <input
            key={teamId}
            name="reportDate"
            type="date"
            defaultValue={todayInTimeZone(team.timezone)}
            required
          />
        </label>
        <label className="field">
          <span>Status</span>
          <select name="status" defaultValue="IN_PROGRESS">
            <option value="NOT_STARTED">Not started</option>
            <option value="IN_PROGRESS">In progress</option>
            <option value="BLOCKED">Blocked</option>
            <option value="READY_FOR_REVIEW">Ready for review</option>
            <option value="DONE">Done</option>
          </select>
        </label>
        <label className="field field-wide">
          <span>Work summary</span>
          <textarea name="workSummary" rows={4} required placeholder="What changed today?" />
        </label>
        <label className="field field-wide">
          <span>Blocker <small>Optional. For Blocked status, the summary is used when this is empty.</small></span>
          <textarea name="blocker" rows={2} placeholder="What is preventing progress?" />
        </label>
        <label className="field field-wide">
          <span>Next action</span>
          <input name="nextAction" required placeholder="The next concrete step" />
        </label>
        <div className="form-actions field-wide">
          <Button appearance="primary" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving..." : "Save daily update"}
          </Button>
          {mutation.isError && <MessageBar intent="error"><MessageBarBody>{mutation.error.message}</MessageBarBody></MessageBar>}
          {saved && <MessageBar intent="success"><MessageBarBody>{saved}</MessageBarBody></MessageBar>}
        </div>
      </form>
    </section>
  );
}

function PageHeading({ eyebrow, title, detail }: { eyebrow: string; title: string; detail: string }) {
  return (
    <div className="section-heading">
      <div><p className="kicker">{eyebrow}</p><h2 id="daily-title">{title}</h2><p>{detail}</p></div>
      <span className="status-chip">Structured evidence</span>
    </div>
  );
}
