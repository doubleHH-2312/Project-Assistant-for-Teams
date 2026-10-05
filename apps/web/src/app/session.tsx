import {
  ProjectAssistantClient,
} from "@project-assistant/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { SessionContext } from "./session-context";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export interface SessionBoundaryProps {
  children: ReactNode;
  loading: ReactNode;
  error: (message: string, retry: () => void) => ReactNode;
  empty: ReactNode;
}

export function SessionBoundary({
  children,
  loading,
  error,
  empty,
}: SessionBoundaryProps) {
  const [userId, setUserId] = useState("user-member-1");
  const [teamId, setTeamId] = useState("");
  const client = useMemo(
    () => new ProjectAssistantClient(apiUrl, userId),
    [userId],
  );
  const query = useQuery({
    queryKey: ["session", userId],
    queryFn: () => client.getSession(),
    retry: false,
  });

  useEffect(() => {
    if (!query.data?.teams.length) {
      setTeamId("");
      return;
    }
    if (!query.data.teams.some((team) => team.teamId === teamId)) {
      setTeamId(query.data.teams[0].teamId);
    }
  }, [query.data, teamId]);

  if (query.isPending) return loading;
  if (query.isError) return error(query.error.message, () => void query.refetch());
  if (!query.data || query.data.teams.length === 0 || !teamId) return empty;
  const team = query.data.teams.find((item) => item.teamId === teamId);
  if (!team) return loading;

  return (
    <SessionContext.Provider
      value={{
        userId,
        setUserId,
        client,
        session: query.data,
        team,
        teamId,
        setTeamId,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}
