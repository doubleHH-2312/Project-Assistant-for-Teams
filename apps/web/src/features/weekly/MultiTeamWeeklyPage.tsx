import { Button, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useMutation } from "@tanstack/react-query";
import type { WeeklyReport } from "@project-assistant/api-client";
import { useState } from "react";
import { useSession } from "../../app/session-context";
import { mondayInTimeZone } from "../../app/team-calendar";
import { WeeklyEditor } from "./WeeklyEditor";

export function MultiTeamWeeklyPage() {
  const { client, session, team } = useSession();
  const eligible = session.teams.filter((team) => team.permissions.includes("GENERATE_MULTI_TEAM_WEEKLY"));
  const [selected, setSelected] = useState<string[]>([]);
  const [weekStart, setWeekStart] = useState(() => mondayInTimeZone(team.timezone));
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const generate = useMutation({ mutationFn: () => client.generateWeekly({ scope: "MULTI_TEAM", teamId: null, teamIds: selected, weekStart, subjectUserId: null }), onSuccess: setReport });
  function toggle(teamId: string) { setSelected((current) => current.includes(teamId) ? current.filter((id) => id !== teamId) : [...current, teamId]); }
  return <section className="panel" aria-labelledby="multi-title"><div className="section-heading"><div><p className="kicker">PRIVATE CHAT WORKFLOW</p><h2 id="multi-title">Multi-team weekly report</h2><p>Select at least two Teams where you hold the required role. Output is grouped by Team, then project.</p></div></div><fieldset className="team-checklist"><legend>Teams to include</legend>{eligible.map((team) => <label className="check-field" key={team.teamId}><input type="checkbox" aria-label={team.teamName} checked={selected.includes(team.teamId)} onChange={() => toggle(team.teamId)} /><span>{team.teamName}<small>{team.role.replace("_", " ")}</small></span></label>)}</fieldset><div className="weekly-controls"><label className="field"><span>Week starts</span><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label><Button appearance="primary" disabled={selected.length < 2 || generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? "Generating..." : "Generate multi-team draft"}</Button></div>{generate.isError && <MessageBar intent="error"><MessageBarBody>{generate.error.message}</MessageBarBody></MessageBar>}{report && <WeeklyEditor client={client} report={report} onChange={setReport} />}</section>;
}
