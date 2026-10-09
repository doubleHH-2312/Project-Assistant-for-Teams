import { Button, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useMutation } from "@tanstack/react-query";
import type { ProjectAssistantClient, ReportScope, WeeklyReport } from "@project-assistant/api-client";
import { useState } from "react";
import { mondayInTimeZone } from "../../app/team-calendar";
import { WeeklyEditor } from "./WeeklyEditor";

export function WeeklyPage({ client, scope, teamId, timeZone, title, description }: { client: ProjectAssistantClient; scope: ReportScope; teamId: string; timeZone: string; title: string; description: string }) {
  const [weekStart, setWeekStart] = useState(() => mondayInTimeZone(timeZone));
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const generate = useMutation({ mutationFn: () => client.generateWeekly({ scope, teamId, teamIds: [], weekStart, subjectUserId: null }), onSuccess: setReport });
  return <section className="panel" aria-labelledby="weekly-title"><div className="section-heading"><div><p className="kicker">HUMAN REVIEW REQUIRED</p><h2 id="weekly-title">{title}</h2><p>{description}</p></div></div><div className="weekly-controls"><label className="field"><span>Week starts</span><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label><Button appearance="primary" onClick={() => generate.mutate()} disabled={generate.isPending}>{generate.isPending ? "Generating..." : "Generate draft"}</Button></div>{generate.isError && <MessageBar intent="error"><MessageBarBody>{generate.error.message}</MessageBarBody></MessageBar>}{!report && !generate.isPending && <p className="empty">No draft generated. The LLM can transform supplied evidence but cannot create project facts.</p>}{report && <WeeklyEditor client={client} report={report} teamId={teamId} onChange={setReport} />}</section>;
}
