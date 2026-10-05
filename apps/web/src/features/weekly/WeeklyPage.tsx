import { Button, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useMutation } from "@tanstack/react-query";
import type { ProjectAssistantClient, ReportScope, WeeklyReport } from "@project-assistant/api-client";
import { useState } from "react";
import { WeeklyEditor } from "./WeeklyEditor";

function monday(): string { const value = new Date(); const day = value.getDay() || 7; value.setDate(value.getDate() - day + 1); return value.toISOString().slice(0, 10); }

export function WeeklyPage({ client, scope, teamId, title, description }: { client: ProjectAssistantClient; scope: ReportScope; teamId: string; title: string; description: string }) {
  const [weekStart, setWeekStart] = useState(monday());
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const generate = useMutation({ mutationFn: () => client.generateWeekly({ scope, teamId, teamIds: [], weekStart, subjectUserId: null }), onSuccess: setReport });
  return <section className="panel" aria-labelledby="weekly-title"><div className="section-heading"><div><p className="kicker">HUMAN REVIEW REQUIRED</p><h2 id="weekly-title">{title}</h2><p>{description}</p></div></div><div className="weekly-controls"><label className="field"><span>Week starts</span><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label><Button appearance="primary" onClick={() => generate.mutate()} disabled={generate.isPending}>{generate.isPending ? "Generating..." : "Generate draft"}</Button></div>{generate.isError && <MessageBar intent="error"><MessageBarBody>{generate.error.message}</MessageBarBody></MessageBar>}{!report && !generate.isPending && <p className="empty">No draft generated. The LLM can transform supplied evidence but cannot create project facts.</p>}{report && <WeeklyEditor client={client} report={report} teamId={teamId} onChange={setReport} />}</section>;
}
