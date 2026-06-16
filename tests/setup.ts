import "@testing-library/jest-dom";

// jsdom emits a "Not implemented: navigation to another Document" warning when
// an anchor's `.click()` triggers a download. Suppress it — it's expected
// because jsdom has no real navigation stack.
const originalError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  if (
    typeof args[0] === "string" &&
    args[0].includes("Not implemented: navigation to another Document")
  ) {
    return;
  }
  originalError(...args);
};
