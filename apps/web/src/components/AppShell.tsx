import { Badge, Button } from "@fluentui/react-components";
import type { Permission, SessionSnapshot, TeamAccess } from "@project-assistant/api-client";
import type { ReactNode } from "react";
import { navigationItems, type AppView } from "../app/router";
import { TeamSelector } from "./TeamSelector";

const integrationMode =
  import.meta.env.VITE_AUTH_MODE === "entra" ? "Entra / live" : "Local / mock";

export function AppShell({
  session,
  team,
  teamId,
  onTeamChange,
  userId,
  onUserChange,
  view,
  onViewChange,
  children,
}: {
  session: SessionSnapshot;
  team: TeamAccess;
  teamId: string;
  onTeamChange: (value: string) => void;
  userId: string;
  onUserChange: (value: string) => void;
  view: AppView;
  onViewChange: (view: AppView) => void;
  children: ReactNode;
}) {
  const permissions = new Set<Permission>(
    session.teams.flatMap((membership) => membership.permissions),
  );
  const available = navigationItems.filter((item) =>
    item.id === "multi-team-weekly"
      ? permissions.has(item.permission)
      : team.permissions.includes(item.permission),
  );

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="topbar">
        <div className="brand-block">
          <span className="product-mark" aria-hidden="true">PA</span>
          <div>
            <h1>Project Assistant</h1>
            <p>Structured updates and evidence-based weekly reports.</p>
          </div>
        </div>
        <div className="session-meta">
          <Badge appearance="tint" color="informative">
            {integrationMode}
          </Badge>
          <span className="identity-label">{session.name}</span>
        </div>
      </header>

      <div className="context-bar">
        <TeamSelector teams={session.teams} value={teamId} onChange={onTeamChange} />
        {import.meta.env.VITE_AUTH_MODE !== "entra" && (
          <label className="compact-field" htmlFor="dev-user">
            <span>Demo identity</span>
            <select
              id="dev-user"
              value={userId}
              onChange={(event) => onUserChange(event.target.value)}
            >
              <option value="user-member-1">Member 1</option>
              <option value="user-member-2">Member 2</option>
              <option value="user-lead">Tech Lead</option>
              <option value="user-pm">PM</option>
            </select>
          </label>
        )}
        <div className="team-context" aria-label="Selected Team role">
          <span>{team.timezone}</span>
          <strong>{team.role.replace("_", " ")}</strong>
        </div>
      </div>

      <div className="application-grid">
        <nav className="side-navigation" aria-label="Project Assistant sections">
          {available.map((item) => (
            <Button
              key={item.id}
              appearance={view === item.id ? "primary" : "subtle"}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => onViewChange(item.id)}
            >
              {item.label}
            </Button>
          ))}
        </nav>
        <main id="main-content" className="workspace" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
