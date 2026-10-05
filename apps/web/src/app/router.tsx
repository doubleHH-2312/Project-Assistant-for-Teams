import type { Permission } from "@project-assistant/api-client";

export type AppView =
  | "daily"
  | "history"
  | "overview"
  | "member-weekly"
  | "team-weekly"
  | "multi-team-weekly"
  | "settings";

export interface NavigationItem {
  id: AppView;
  label: string;
  permission: Permission;
}

export const navigationItems: readonly NavigationItem[] = [
  { id: "daily", label: "Daily update", permission: "SUBMIT_OWN_DAILY" },
  { id: "history", label: "History", permission: "VIEW_OWN_HISTORY" },
  { id: "overview", label: "Team overview", permission: "VIEW_TEAM_DAILY_SUMMARY" },
  { id: "member-weekly", label: "My weekly", permission: "GENERATE_OWN_WEEKLY" },
  { id: "team-weekly", label: "Team weekly", permission: "GENERATE_TEAM_WEEKLY" },
  {
    id: "multi-team-weekly",
    label: "Multi-team weekly",
    permission: "GENERATE_MULTI_TEAM_WEEKLY",
  },
  { id: "settings", label: "Team settings", permission: "MANAGE_TEAMS_BINDING" },
];
