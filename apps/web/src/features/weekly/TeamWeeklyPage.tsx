import { useSession } from "../../app/session-context";
import { WeeklyPage } from "./WeeklyPage";
export function TeamWeeklyPage() { const { client, team, teamId } = useSession(); return <WeeklyPage key={teamId} client={client} scope="TEAM" teamId={teamId} timeZone={team.timezone} title="Team weekly report" description="Aggregate only confirmed member reports, grouped by project, then review and confirm." />; }
