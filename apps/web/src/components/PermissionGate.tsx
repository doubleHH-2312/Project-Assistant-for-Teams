import type { Permission } from "@project-assistant/api-client";
import type { ReactNode } from "react";
import { AsyncState } from "./AsyncState";

export function PermissionGate({
  permissions,
  requires,
  children,
}: {
  permissions: readonly Permission[];
  requires: Permission;
  children: ReactNode;
}) {
  if (!permissions.includes(requires)) {
    return (
      <AsyncState
        kind="forbidden"
        title="Access restricted"
        detail="Your role does not have permission to use this feature for the selected Team."
      />
    );
  }
  return children;
}
