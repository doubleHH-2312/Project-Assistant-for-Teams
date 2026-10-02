import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders an accessible daily reporting workspace", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { name: "Project Assistant" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Daily update" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByLabelText("Work summary")).toBeInTheDocument();
    expect(screen.getByText(/Integration mode/i)).toBeInTheDocument();
  });
});
