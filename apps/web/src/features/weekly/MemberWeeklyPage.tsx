import { useSession } from "../../app/session-context";
import { WeeklyPage } from "./WeeklyPage";
export function MemberWeeklyPage() { const { client, team, teamId } = useSession(); return <WeeklyPage key={teamId} client={client} scope="MEMBER" teamId={teamId} timeZone={team.timezone} title="My weekly report" description="Generate a Team-scoped draft from your Daily evidence, review it, then confirm it." />; }
