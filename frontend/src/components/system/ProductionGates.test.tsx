import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProductionGates } from "./ProductionGates";

describe("ProductionGates", () => {
  it("renders readable gate names and explicit status badges", () => {
    render(
      <ProductionGates
        gates={[
          {
            name: "纸面收益",
            status: "阻断",
            tone: "bad",
            detail: "纸面收益为负：当前验证收益率 -2.5%。",
          },
        ]}
        overallTone="bad"
        overallLabel="继续验证"
      />,
    );

    expect(screen.getByText("纸面收益")).toBeInTheDocument();
    expect(screen.getByText("阻断")).toBeInTheDocument();
    expect(screen.queryByText("未识别状态")).not.toBeInTheDocument();
  });
});
