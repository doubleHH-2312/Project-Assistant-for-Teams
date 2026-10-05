import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PermissionGate } from "./PermissionGate";

describe("PermissionGate", () => {
  it("renders an explicit forbidden state when access is missing", () => {
    render(
      <PermissionGate
        permissions={["SUBMIT_OWN_DAILY"]}
        requires="GENERATE_TEAM_WEEKLY"
      >
        protected
      </PermissionGate>,
    );

    expect(screen.getByRole("heading", { name: "Access restricted" })).toBeInTheDocument();
    expect(screen.queryByText("protected")).not.toBeInTheDocument();
  });
});
