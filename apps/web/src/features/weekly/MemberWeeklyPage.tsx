import { useSession } from "../../app/session-context";
import { WeeklyPage } from "./WeeklyPage";
export function MemberWeeklyPage() { const { client, teamId } = useSession(); return <WeeklyPage client={client} scope="MEMBER" teamId={teamId} title="My weekly report" description="Generate a Team-scoped draft from your Daily evidence, review it, then confirm it." />; }
