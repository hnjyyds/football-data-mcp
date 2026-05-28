import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TeamLogo } from "./TeamLogo";

describe("TeamLogo", () => {
  it("renders initials when no logoUrl provided", () => {
    render(<TeamLogo name="Real Madrid" />);
    expect(screen.getByText("RM")).toBeInTheDocument();
  });

  it("renders <img> with given logoUrl", () => {
    const { container } = render(<TeamLogo name="Real Madrid" logoUrl="https://example.com/rm.png" />);
    const img = container.querySelector("img") as HTMLImageElement;
    expect(img).not.toBeNull();
    expect(img.src).toContain("rm.png");
  });

  it("falls back to initials when image fails to load", () => {
    const { container } = render(<TeamLogo name="Real Madrid" logoUrl="https://example.com/missing.png" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    fireEvent.error(img!);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("RM")).toBeInTheDocument();
  });

  it("preserves aria-label for screen readers", () => {
    render(<TeamLogo name="Manchester City" />);
    expect(screen.getByLabelText("Manchester City 队徽")).toBeInTheDocument();
  });
});
