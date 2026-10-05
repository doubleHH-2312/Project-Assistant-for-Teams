import { useSession } from "../../app/session-context";
import { WeeklyPage } from "./WeeklyPage";
export function TeamWeeklyPage() { const { client, teamId } = useSession(); return <WeeklyPage client={client} scope="TEAM" teamId={teamId} title="Team weekly report" description="Aggregate only confirmed member reports, grouped by project, then review and confirm." />; }
