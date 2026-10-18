import { describe, expect, it } from "vitest";
import { reportFilename } from "./pages/ReportsPage";

describe("report download behavior", () => {
  it("creates stable download names for each report type", () => {
    expect(reportFilename("p1", "project-summary")).toBe("devflow-p1-project-summary.pdf");
    expect(reportFilename("p1", "change-impact", "c1")).toBe("devflow-p1-change-impact-c1.pdf");
  });
});
