import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ProjectAssistantClient,
  type DailyReportInput,
  type TeamOverview,
  type WeeklyReport,
  type WorkStatus,
} from "@project-assistant/api-client";

type View = "daily" | "overview" | "weekly";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const integrationMode = import.meta.env.VITE_AUTH_MODE === "entra" ? "Entra / live" : "Local / mock";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function mondayOfCurrentWeek(): string {
  const value = new Date();
  const day = value.getDay() || 7;
  value.setDate(value.getDate() - day + 1);
  return value.toISOString().slice(0, 10);
}

export function App() {
  const [view, setView] = useState<View>("daily");
  const [userId, setUserId] = useState("user-member-1");
  const client = useMemo(() => new ProjectAssistantClient(apiUrl, userId), [userId]);

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="topbar">
        <div>
          <p className="eyebrow">PROJECT OPERATIONS</p>
          <h1>Project Assistant</h1>
          <p className="subtitle">Daily evidence, clear blockers, reviewable weekly reports.</p>
        </div>
        <div className="session-controls">
          <span className="mode-badge">Integration mode: {integrationMode}</span>
          <label htmlFor="dev-user">Demo identity</label>
          <select id="dev-user" value={userId} onChange={(event) => setUserId(event.target.value)}>
            <option value="user-member-1">Member 1</option>
            <option value="user-member-2">Member 2</option>
            <option value="user-lead">Tech Lead</option>
            <option value="user-pm">PM</option>
          </select>
        </div>
      </header>

      <nav className="tabs" role="tablist" aria-label="Project Assistant sections">
        <Tab active={view === "daily"} onClick={() => setView("daily")}>Daily update</Tab>
        <Tab active={view === "overview"} onClick={() => setView("overview")}>Team overview</Tab>
        <Tab active={view === "weekly"} onClick={() => setView("weekly")}>Weekly reports</Tab>
      </nav>

      <main id="main-content" className="workspace" tabIndex={-1}>
        {view === "daily" && <DailyUpdate client={client} />}
        {view === "overview" && <Overview client={client} />}
        {view === "weekly" && <Weekly client={client} />}
      </main>
    </div>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return <button role="tab" aria-selected={active} className="tab" onClick={onClick} type="button">{children}</button>;
}

function DailyUpdate({ client }: { client: ProjectAssistantClient }) {
  const [success, setSuccess] = useState("");
  const mutation = useMutation({
    mutationFn: (input: DailyReportInput) => client.createDailyReport(input),
    onSuccess: (report) => setSuccess(`Saved ${report.workItemId} for ${report.reportDate}.`),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess("");
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      projectId: String(data.get("projectId")),
      workItemId: String(data.get("workItemId")),
      reportDate: String(data.get("reportDate")),
      status: String(data.get("status")) as WorkStatus,
      workSummary: String(data.get("workSummary")),
      blocker: String(data.get("blocker") || "") || null,
      nextAction: String(data.get("nextAction")),
    });
  }

  return (
    <section className="panel" aria-labelledby="daily-title">
      <div className="section-heading">
        <div><p className="kicker">MEMBER WORKFLOW</p><h2 id="daily-title">Record today in under two minutes</h2></div>
        <span className="status-chip">One record per work item</span>
      </div>
      <form className="report-form" onSubmit={submit}>
        <Field label="Project ID" name="projectId" defaultValue="project-mvp" />
        <Field label="Work item ID" name="workItemId" defaultValue="work-item-01" />
        <Field label="Reporting date" name="reportDate" type="date" defaultValue={isoToday()} />
        <label className="field"><span>Status</span><select name="status" defaultValue="IN_PROGRESS"><option value="NOT_STARTED">Not started</option><option value="IN_PROGRESS">In progress</option><option value="BLOCKED">Blocked</option><option value="READY_FOR_REVIEW">Ready for review</option><option value="DONE">Done</option></select></label>
        <label className="field field-wide"><span>Work summary</span><textarea name="workSummary" rows={4} required placeholder="What changed today?" /></label>
        <label className="field field-wide"><span>Blocker <small>Optional; summary is used when status is Blocked</small></span><textarea name="blocker" rows={2} placeholder="What is preventing progress?" /></label>
        <label className="field field-wide"><span>Next action</span><input name="nextAction" required placeholder="The next concrete step" /></label>
        <div className="form-actions field-wide">
          <button className="primary-button" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Saving…" : "Save daily update"}</button>
          {mutation.error && <p className="feedback error" role="alert">{mutation.error.message}</p>}
          {success && <p className="feedback success" role="status">{success}</p>}
        </div>
      </form>
    </section>
  );
}

function Field({ label, name, type = "text", defaultValue }: { label: string; name: string; type?: string; defaultValue?: string }) {
  return <label className="field"><span>{label}</span><input name={name} type={type} defaultValue={defaultValue} required /></label>;
}

function Overview({ client }: { client: ProjectAssistantClient }) {
  const reportingDate = isoToday();
  const query = useQuery({ queryKey: ["overview", reportingDate, client], queryFn: () => client.getOverview("team-ops", reportingDate), retry: false });
  if (query.isLoading) return <StatePanel title="Loading team overview…" />;
  if (query.error) return <StatePanel title="Unable to load overview" detail={`${query.error.message} Select the Tech Lead demo identity and retry.`} retry={() => query.refetch()} />;
  if (!query.data) return <StatePanel title="No overview data" />;
  return <OverviewContent overview={query.data} />;
}

function OverviewContent({ overview }: { overview: TeamOverview }) {
  return (
    <section aria-labelledby="overview-title">
      <div className="section-heading"><div><p className="kicker">LEAD CONTROL VIEW</p><h2 id="overview-title">Team overview</h2></div><span className="status-chip">{overview.reportingDate}</span></div>
      <div className="metric-grid">
        <Metric label="Coverage" value={`${overview.coverage.percentage}%`} detail={`${overview.coverage.submitted} of ${overview.coverage.expected}`} />
        <Metric label="Blocked items" value={String(overview.blockers.length)} detail="Requires attention" />
        <Metric label="Missing updates" value={String(overview.missingReporters.length)} detail="Expected reporters" />
        <Metric label="Done records" value={String(overview.statusCounts.DONE ?? 0)} detail="Reported today" />
      </div>
      <div className="two-column">
        <article className="panel"><h3>Active blockers</h3>{overview.blockers.length === 0 ? <p className="empty">No active blockers.</p> : <ul className="evidence-list">{overview.blockers.map((blocker) => <li key={blocker.reportId}><strong>{blocker.workItemId}</strong><span>{blocker.effectiveBlocker}</span><small>{blocker.ageDays} day(s) · Next: {blocker.nextAction}</small></li>)}</ul>}</article>
        <article className="panel"><h3>Missing reporters</h3>{overview.missingReporters.length === 0 ? <p className="empty">Everyone has reported.</p> : <ul className="name-list">{overview.missingReporters.map((person) => <li key={person.id}><span>{person.name}</span><code>{person.id}</code></li>)}</ul>}</article>
      </div>
    </section>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function Weekly({ client }: { client: ProjectAssistantClient }) {
  const [scope, setScope] = useState<"MEMBER" | "TEAM">("MEMBER");
  const [weekStart, setWeekStart] = useState(mondayOfCurrentWeek());
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const generate = useMutation({ mutationFn: () => client.generateWeekly(scope, weekStart), onSuccess: setReport });
  const confirm = useMutation({ mutationFn: (id: string) => client.confirmWeekly(id), onSuccess: setReport });
  return (
    <section className="panel" aria-labelledby="weekly-title">
      <div className="section-heading"><div><p className="kicker">HUMAN-REVIEWED OUTPUT</p><h2 id="weekly-title">Weekly report</h2></div>{report && <span className="status-chip">{report.status}</span>}</div>
      <div className="weekly-controls">
        <label className="field"><span>Scope</span><select value={scope} onChange={(event) => setScope(event.target.value as "MEMBER" | "TEAM")}><option value="MEMBER">Member</option><option value="TEAM">Team</option></select></label>
        <label className="field"><span>Week starts</span><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label>
        <button className="primary-button align-end" disabled={generate.isPending} onClick={() => generate.mutate()} type="button">{generate.isPending ? "Generating…" : "Generate draft"}</button>
      </div>
      {generate.error && <p className="feedback error" role="alert">{generate.error.message}</p>}
      {!report && !generate.isPending && <p className="empty">Generate a draft from authoritative evidence. Nothing is confirmed automatically.</p>}
      {report && <div className="report-preview">{Object.entries(report.contentJson).map(([key, values]) => <section key={key}><h3>{key.replaceAll("_", " ")}</h3>{values.length ? <ul>{values.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="empty">No recorded evidence.</p>}</section>)}<div className="trace">Source: {report.generationSource} · Template v{report.templateVersion} · {report.inputRecordIds.length} input record(s)</div>{report.status !== "CONFIRMED" && <button className="primary-button" disabled={confirm.isPending} onClick={() => confirm.mutate(report.id)} type="button">Confirm report</button>}</div>}
    </section>
  );
}

function StatePanel({ title, detail, retry }: { title: string; detail?: string; retry?: () => void }) {
  return <section className="panel state-panel" role="status"><h2>{title}</h2>{detail && <p>{detail}</p>}{retry && <button className="secondary-button" onClick={retry} type="button">Retry</button>}</section>;
}
