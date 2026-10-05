import type { TeamAccess } from "@project-assistant/api-client";

export function TeamSelector({
  teams,
  value,
  onChange,
}: {
  teams: readonly TeamAccess[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="compact-field" htmlFor="current-team">
      <span>Current Team</span>
      <select
        id="current-team"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {teams.map((team) => (
          <option key={team.teamId} value={team.teamId}>
            {team.teamName} ({team.role.replace("_", " ")})
          </option>
        ))}
      </select>
    </label>
  );
}
