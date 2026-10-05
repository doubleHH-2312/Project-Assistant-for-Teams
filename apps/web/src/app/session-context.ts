import type { ProjectAssistantClient, SessionSnapshot, TeamAccess } from "@project-assistant/api-client";
import { createContext, useContext } from "react";

export interface SessionContextValue {
  userId: string;
  setUserId: (value: string) => void;
  client: ProjectAssistantClient;
  session: SessionSnapshot;
  team: TeamAccess;
  teamId: string;
  setTeamId: (value: string) => void;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used within SessionBoundary");
  return value;
}
