import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  // Prevent rendered trees, fake timers, or globals from leaking between tests.
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
