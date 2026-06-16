import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Resolves the `@/*` path alias from tsconfig.json natively (no plugin needed)
    alias: { "@": "/Users/mosespalacios/Web Apps/label-verification-app" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
