import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { WorkStatus } from "@project-assistant/api-client";
import { useSession } from "../../app/session-context";
import { AsyncState } from "../../components/AsyncState";

function daysAgo(days: number): string {
  const value = new Date();
  value.setDate(value.getDate() - days);
  return value.toISOString().slice(0, 10);
}

export function HistoryPage() {
  const { client, teamId } = useSession();
  const [dateFrom, setDateFrom] = useState(daysAgo(30));
  const [dateTo, setDateTo] = useState(daysAgo(0));
  const [status, setStatus] = useState<WorkStatus | "">("");
  const query = useQuery({
    queryKey: ["daily-history", teamId, dateFrom, dateTo, status],
    queryFn: () => client.listDailyHistory({ teamId, dateFrom, dateTo, status: status || undefined }),
    retry: false,
  });

  return (
    <section aria-labelledby="history-title">
      <div className="section-heading">
        <div><p className="kicker">AUDITABLE TIMELINE</p><h2 id="history-title">Daily history</h2><p>Report dates are stored by the system and remain attached to the original evidence.</p></div>
      </div>
      <div className="filter-bar panel">
        <label className="field"><span>From</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
        <label className="field"><span>To</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
        <label className="field"><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value as WorkStatus | "")}><option value="">All statuses</option><option value="IN_PROGRESS">In progress</option><option value="BLOCKED">Blocked</option><option value="READY_FOR_REVIEW">Ready for review</option><option value="DONE">Done</option></select></label>
      </div>
      {query.isPending ? <AsyncState kind="loading" title="Loading daily history" /> : null}
      {query.isError ? <AsyncState kind="error" title="History is unavailable" detail={query.error.message} retry={() => void query.refetch()} /> : null}
      {query.data?.length === 0 ? <AsyncState title="No reports match these filters" detail="Adjust the date range or status filter." /> : null}
      {query.data && query.data.length > 0 ? (
        <ol className="timeline">
          {query.data.map((report) => (
            <li key={report.id} className="panel timeline-entry">
              <time dateTime={report.reportDate}>{report.reportDate}</time>
              <div className="timeline-body">
                <div className="entry-heading"><strong>{report.workItemId}</strong><span className={`status-chip status-${report.status.toLowerCase()}`}>{report.status.replaceAll("_", " ")}</span></div>
                <p>{report.workSummary}</p>
                {report.effectiveBlocker && report.effectiveBlocker !== report.workSummary && <p className="blocker"><strong>Blocker:</strong> {report.effectiveBlocker}</p>}
                <small>Next: {report.nextAction}</small>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
