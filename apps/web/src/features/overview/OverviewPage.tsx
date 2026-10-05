import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSession } from "../../app/session-context";
import { AsyncState } from "../../components/AsyncState";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OverviewPage() {
  const { client, teamId } = useSession();
  const [reportingDate, setReportingDate] = useState(today());
  const query = useQuery({
    queryKey: ["overview", teamId, reportingDate],
    queryFn: () => client.getOverview(teamId, reportingDate),
    retry: false,
  });

  if (query.isPending) return <AsyncState kind="loading" title="Loading Team overview" />;
  if (query.isError) return <AsyncState kind="error" title="Team overview is unavailable" detail={query.error.message} retry={() => void query.refetch()} />;
  if (!query.data) return <AsyncState title="No overview is available" />;
  const overview = query.data;
  return (
    <section aria-labelledby="overview-title">
      <div className="section-heading">
        <div><p className="kicker">TEAM SIGNALS</p><h2 id="overview-title">Team overview</h2><p>Coverage and blockers from structured Daily evidence.</p></div>
        <label className="field date-filter"><span>Reporting date</span><input type="date" value={reportingDate} onChange={(event) => setReportingDate(event.target.value)} /></label>
      </div>
      <div className="metric-grid">
        <Metric label="Coverage" value={`${overview.coverage.percentage}%`} detail={`${overview.coverage.submitted} of ${overview.coverage.expected}`} />
        <Metric label="Blocked" value={String(overview.blockers.length)} detail="Items needing attention" />
        <Metric label="Missing" value={String(overview.missingReporters.length)} detail="Expected reporters" />
        <Metric label="Done" value={String(overview.statusCounts.DONE ?? 0)} detail="Records on this date" />
      </div>
      <div className="two-column">
        <article className="panel"><h3>Active blockers</h3>{overview.blockers.length === 0 ? <p className="empty">No active blockers.</p> : <ul className="evidence-list">{overview.blockers.map((item) => <li key={item.reportId}><strong>{item.workItemId}</strong><span>{item.effectiveBlocker}</span><small>Blocked since {item.blockedSince}. Next: {item.nextAction}</small></li>)}</ul>}</article>
        <article className="panel"><h3>Missing reporters</h3>{overview.missingReporters.length === 0 ? <p className="empty">Everyone has reported.</p> : <ul className="name-list">{overview.missingReporters.map((person) => <li key={person.id}><span>{person.name}</span><code>{person.id}</code></li>)}</ul>}</article>
      </div>
    </section>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}
