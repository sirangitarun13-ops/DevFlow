import { describe, expect, it } from "vitest";
import { boundedPercent, distributionTotal } from "./pages/AnalyticsPage";

describe("analytics presentation helpers", () => {
  it("totals grouped metric distributions", () => {
    expect(distributionTotal({ todo: 2, completed: 3 })).toBe(5);
    expect(distributionTotal({})).toBe(0);
  });

  it("bounds progress indicators to a safe percentage", () => {
    expect(boundedPercent(-5)).toBe(0);
    expect(boundedPercent(42.5)).toBe(42.5);
    expect(boundedPercent(120)).toBe(100);
  });
});
