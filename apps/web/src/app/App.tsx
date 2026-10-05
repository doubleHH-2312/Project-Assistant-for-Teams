import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { AsyncState } from "../components/AsyncState";
import { PermissionGate } from "../components/PermissionGate";
import { DailyPage } from "../features/daily/DailyPage";
import { HistoryPage } from "../features/history/HistoryPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { TeamSettingsPage } from "../features/settings/TeamSettingsPage";
import { MemberWeeklyPage } from "../features/weekly/MemberWeeklyPage";
import { MultiTeamWeeklyPage } from "../features/weekly/MultiTeamWeeklyPage";
import { TeamWeeklyPage } from "../features/weekly/TeamWeeklyPage";
import { navigationItems, type AppView } from "./router";
import { useSession } from "./session-context";
import { SessionBoundary } from "./session";

export function App() {
  return (
    <SessionBoundary
      loading={<div className="boot-state"><AsyncState kind="loading" title="Loading your workspace" /></div>}
      error={(message, retry) => <div className="boot-state"><AsyncState kind="error" title="Session is unavailable" detail={message} retry={retry} /></div>}
      empty={<div className="boot-state"><AsyncState title="No Team access" detail="Ask a PM to add your Team membership." /></div>}
    >
      <AuthorizedApplication />
    </SessionBoundary>
  );
}

function AuthorizedApplication() {
  const { session, team, teamId, setTeamId, userId, setUserId } = useSession();
  const [view, setView] = useState<AppView>("daily");
  const route = navigationItems.find((item) => item.id === view)!;
  const multiTeamAllowed = session.teams.some((item) => item.permissions.includes(route.permission));
  const allowed = view === "multi-team-weekly" ? multiTeamAllowed : team.permissions.includes(route.permission);

  useEffect(() => {
    if (!allowed) {
      const fallback = navigationItems.find((item) => team.permissions.includes(item.permission));
      if (fallback) setView(fallback.id);
    }
  }, [allowed, team]);

  return (
    <AppShell session={session} team={team} teamId={teamId} onTeamChange={setTeamId} userId={userId} onUserChange={setUserId} view={view} onViewChange={setView}>
      <PermissionGate permissions={allowed ? [route.permission] : []} requires={route.permission}>
        {view === "daily" && <DailyPage />}
        {view === "history" && <HistoryPage />}
        {view === "overview" && <OverviewPage />}
        {view === "member-weekly" && <MemberWeeklyPage />}
        {view === "team-weekly" && <TeamWeeklyPage />}
        {view === "multi-team-weekly" && <MultiTeamWeeklyPage />}
        {view === "settings" && <TeamSettingsPage />}
      </PermissionGate>
    </AppShell>
  );
}
