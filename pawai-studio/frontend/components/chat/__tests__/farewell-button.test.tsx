/**
 * 學校 demo (6/22) FarewellButton — 結尾「道別」鈕。
 *
 * vitest 環境為 "node"（無 jsdom），故與 gesture-toggle.test.tsx 同慣例，只測
 * pure 請求 builder；fetch wiring 在 gateway 層（test_demo_controls.py）驗證。
 */
import { describe, it, expect } from "vitest";
import { buildFarewellRequest } from "../farewell-button";

describe("buildFarewellRequest", () => {
  it("POSTs to /api/farewell_action（一次性 action、無 body）", () => {
    const { url } = buildFarewellRequest();
    expect(url).toMatch(/\/api\/farewell_action$/);
  });
});
