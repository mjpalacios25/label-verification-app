import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatLandingPage, {
  dedupeFiles,
  formatBytes,
  isVerificationResult,
} from "@/app/chat/page";

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------
vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal File-like object without touching the real File constructor */
function makeFile(
  name: string,
  size: number,
  type: string,
  lastModified = 0,
): File {
  const blob = new Blob(["x".repeat(size)], { type });
  return new File([blob], name, { type, lastModified });
}

function makeJpeg(name = "label.jpg", size = 1024): File {
  return makeFile(name, size, "image/jpeg");
}

function makePdf(name = "approval.pdf", size = 2048): File {
  return makeFile(name, size, "application/pdf");
}

/** Return a resolved fetch mock that produces `{ ok: true, json: () => data }` */
function mockFetchOk(data: unknown): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(data),
    blob: vi.fn().mockResolvedValue(new Blob(["a,b,c"], { type: "text/csv" })),
  });
}

/** Return a resolved fetch mock that produces `{ ok: false, status }` */
function mockFetchError(status = 500): ReturnType<typeof vi.fn> {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: vi.fn().mockResolvedValue({}),
    blob: vi.fn().mockResolvedValue(new Blob()),
  });
}

/** Return a rejected fetch mock (network failure) */
function mockFetchNetworkFailure(): ReturnType<typeof vi.fn> {
  return vi.fn().mockRejectedValue(new Error("Failed to fetch"));
}

// ---------------------------------------------------------------------------
// Pure function tests
// ---------------------------------------------------------------------------

describe("dedupeFiles", () => {
  it("returns the existing array unchanged when incoming is empty", () => {
    const existing = [makeJpeg("a.jpg")];
    const result = dedupeFiles(existing, []);
    expect(result).toBe(existing);
  });

  it("merges arrays without duplicates when the same file is added twice", () => {
    const file = makeJpeg("label.jpg", 1024);
    const duplicate = makeJpeg("label.jpg", 1024);
    const result = dedupeFiles([file], [duplicate]);
    expect(result).toHaveLength(1);
    expect(result[0]).toBe(file);
  });

  it("preserves the order of the first occurrence", () => {
    const first = makeJpeg("a.jpg", 100);
    const second = makeJpeg("b.jpg", 200);
    const duplicate = makeJpeg("a.jpg", 100);
    const result = dedupeFiles([first, second], [duplicate]);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("a.jpg");
    expect(result[1].name).toBe("b.jpg");
  });

  it("allows files with the same name but different size", () => {
    const small = makeJpeg("label.jpg", 500);
    const large = makeJpeg("label.jpg", 1500);
    const result = dedupeFiles([small], [large]);
    expect(result).toHaveLength(2);
  });

  it("treats files with the same name and size as duplicates even if lastModified differs", () => {
    // dedupeFiles keys on name:size — lastModified is not part of the key
    const original = makeFile("label.jpg", 1024, "image/jpeg", 1000);
    const later = makeFile("label.jpg", 1024, "image/jpeg", 9999);
    const result = dedupeFiles([original], [later]);
    expect(result).toHaveLength(1);
  });

  it("appends genuinely new files to the end of the existing list", () => {
    const a = makeJpeg("a.jpg", 100);
    const b = makeJpeg("b.jpg", 200);
    const c = makeJpeg("c.jpg", 300);
    const result = dedupeFiles([a, b], [c]);
    expect(result).toHaveLength(3);
    expect(result[2].name).toBe("c.jpg");
  });

  it("deduplicates within the incoming list itself", () => {
    const a = makeJpeg("a.jpg", 100);
    const aDupe = makeJpeg("a.jpg", 100);
    const result = dedupeFiles([], [a, aDupe]);
    expect(result).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------

describe("formatBytes", () => {
  it('formats 0 as "0 B"', () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it('formats 1023 as "1023 B"', () => {
    expect(formatBytes(1023)).toBe("1023 B");
  });

  it('formats 1024 as "1.0 KB"', () => {
    expect(formatBytes(1024)).toBe("1.0 KB");
  });

  it('formats 1048576 (1 MiB) as "1.0 MB"', () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });

  it("formats values just below 1 KB boundary correctly", () => {
    expect(formatBytes(1)).toBe("1 B");
  });

  it("formats values in the KB range with one decimal", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });

  it("formats large values in the MB range with one decimal", () => {
    expect(formatBytes(2097152)).toBe("2.0 MB");
  });
});

// ---------------------------------------------------------------------------

describe("isVerificationResult", () => {
  it("returns true for a valid result object", () => {
    expect(
      isVerificationResult({
        brand_match: "yes",
        alcohol_match: "no",
        warning_match: "yes",
      }),
    ).toBe(true);
  });

  it("returns false for null", () => {
    expect(isVerificationResult(null)).toBe(false);
  });

  it("returns false for an empty object", () => {
    expect(isVerificationResult({})).toBe(false);
  });

  it("returns false when brand_match is present but alcohol_match is missing", () => {
    expect(
      isVerificationResult({ brand_match: "yes", warning_match: "yes" }),
    ).toBe(false);
  });

  it("returns false when alcohol_match is present but brand_match is missing", () => {
    expect(
      isVerificationResult({ alcohol_match: "yes", warning_match: "yes" }),
    ).toBe(false);
  });

  it("returns false when warning_match is present but brand_match is missing", () => {
    expect(
      isVerificationResult({ brand_match: "yes", alcohol_match: "yes" }),
    ).toBe(false);
  });

  it("returns false for a plain string", () => {
    expect(isVerificationResult("yes")).toBe(false);
  });

  it("returns false for a number", () => {
    expect(isVerificationResult(42)).toBe(false);
  });

  it("returns false for an array", () => {
    expect(isVerificationResult([])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Component tests
// ---------------------------------------------------------------------------

describe("ChatLandingPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Reset fetch to a no-op so individual tests opt in to specific behavior
    global.fetch = vi.fn();
  });

  // -------------------------------------------------------------------------
  // Initial render
  // -------------------------------------------------------------------------
  describe("initial state", () => {
    it("renders the page heading", () => {
      render(<ChatLandingPage />);
      expect(
        screen.getByRole("heading", { name: /alcohol label verification/i }),
      ).toBeInTheDocument();
    });

    it("renders the verify button in a disabled state", () => {
      render(<ChatLandingPage />);
      const btn = screen.getByRole("button", {
        name: /start verifying labels/i,
      });
      expect(btn).toBeDisabled();
    });

    it("does not show a results panel on mount", () => {
      render(<ChatLandingPage />);
      expect(
        screen.queryByRole("heading", { name: /verification results/i }),
      ).not.toBeInTheDocument();
    });

    it("does not show an error on mount", () => {
      render(<ChatLandingPage />);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // File selection
  // -------------------------------------------------------------------------
  describe("file selection", () => {
    it("displays the image filename after selecting a JPEG", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      await user.upload(input, makeJpeg("my-label.jpg", 2048));

      expect(screen.getByText("my-label.jpg")).toBeInTheDocument();
    });

    it("displays the PDF filename after selecting a PDF", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;
      await user.upload(input, makePdf("approval-form.pdf", 4096));

      expect(screen.getByText("approval-form.pdf")).toBeInTheDocument();
    });

    it("keeps the verify button disabled when only an image is selected", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      await user.upload(input, makeJpeg());

      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeDisabled();
    });

    it("keeps the verify button disabled when only a PDF is selected", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;
      await user.upload(input, makePdf());

      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeDisabled();
    });

    it("enables the verify button once both an image and a PDF are selected", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg());
      await user.upload(pdfInput, makePdf());

      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeEnabled();
    });

    it("shows a count of selected images", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      await user.upload(input, [makeJpeg("a.jpg"), makeJpeg("b.jpg", 500)]);

      expect(screen.getByText(/2 images selected/i)).toBeInTheDocument();
    });

    it("disables the verify button again after removing the only image", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg("label.jpg"));
      await user.upload(pdfInput, makePdf());

      // Button should be enabled now
      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeEnabled();

      // Remove the image using its aria-label remove button
      const removeBtn = screen.getByRole("button", {
        name: /remove image label\.jpg/i,
      });
      await user.click(removeBtn);

      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeDisabled();
    });

    it("does not add duplicate images (same name and size)", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;

      // Upload the same file twice
      await user.upload(input, makeJpeg("label.jpg", 1024));
      await user.upload(input, makeJpeg("label.jpg", 1024));

      expect(screen.getByText(/1 image selected/i)).toBeInTheDocument();
    });

    it("clears all images when 'Clear all' is clicked", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const input = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      await user.upload(input, [makeJpeg("a.jpg"), makeJpeg("b.jpg", 500)]);

      expect(screen.getByText(/2 images selected/i)).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /clear all/i }));

      expect(
        screen.queryByText(/images selected/i),
      ).not.toBeInTheDocument();
    });

    it("removes a PDF when its remove button is clicked", async () => {
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;
      await user.upload(pdfInput, makePdf("form.pdf"));

      expect(screen.getByText("form.pdf")).toBeInTheDocument();

      await user.click(
        screen.getByRole("button", { name: /remove form form\.pdf/i }),
      );

      expect(screen.queryByText("form.pdf")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Verify flow — success
  // -------------------------------------------------------------------------
  describe("verify flow — success", () => {
    async function setupAndVerify(result: unknown) {
      global.fetch = mockFetchOk(result);
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg());
      await user.upload(pdfInput, makePdf());

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      return user;
    }

    it("shows the results panel after a successful verification", async () => {
      await setupAndVerify({
        brand_match: "yes",
        alcohol_match: "yes",
        warning_match: "no",
      });

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /verification results/i }),
        ).toBeInTheDocument();
      });
    });

    it("shows Match for brand_match: yes", async () => {
      await setupAndVerify({
        brand_match: "yes",
        alcohol_match: "yes",
        warning_match: "yes",
      });

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /verification results/i }),
        ).toBeInTheDocument();
      });

      const resultSection = screen
        .getByRole("heading", { name: /verification results/i })
        .closest("section") as HTMLElement;

      expect(within(resultSection).getByText("Brand Name Match")).toBeInTheDocument();
      // All three are "yes" → all should say "Match"
      const matchLabels = within(resultSection).getAllByText("Match");
      expect(matchLabels).toHaveLength(3);
    });

    it("shows No match for warning_match: no", async () => {
      await setupAndVerify({
        brand_match: "yes",
        alcohol_match: "yes",
        warning_match: "no",
      });

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /verification results/i }),
        ).toBeInTheDocument();
      });

      const resultSection = screen
        .getByRole("heading", { name: /verification results/i })
        .closest("section") as HTMLElement;

      expect(within(resultSection).getByText("No match")).toBeInTheDocument();
    });

    it("POSTs to /verify with the image and PDF in the FormData", async () => {
      global.fetch = mockFetchOk({
        brand_match: "yes",
        alcohol_match: "yes",
        warning_match: "yes",
      });
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg("test.jpg"));
      await user.upload(pdfInput, makePdf("test.pdf"));
      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          "http://localhost:8000/verify",
          expect.objectContaining({ method: "POST" }),
        );
      });

      const [, callOptions] = (global.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0];
      const formData = callOptions.body as FormData;
      expect(formData.get("form")).toBeTruthy();
      expect(formData.getAll("images")).toHaveLength(1);
    });

    it("does not show an error after a successful verify", async () => {
      await setupAndVerify({
        brand_match: "yes",
        alcohol_match: "no",
        warning_match: "no",
      });

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /verification results/i }),
        ).toBeInTheDocument();
      });

      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Verify flow — in-flight state
  // -------------------------------------------------------------------------
  describe("verify flow — in-flight state", () => {
    it('shows "Verifying…" on the button while the fetch is pending', async () => {
      // Fetch never resolves — we just check the in-flight state
      let resolvePromise!: (v: unknown) => void;
      global.fetch = vi.fn().mockReturnValue(
        new Promise((res) => {
          resolvePromise = res;
        }),
      );

      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg());
      await user.upload(pdfInput, makePdf());

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      expect(await screen.findByText("Verifying…")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /verifying/i }),
      ).toBeDisabled();

      // Resolve so the component can settle
      resolvePromise({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          brand_match: "yes",
          alcohol_match: "yes",
          warning_match: "yes",
        }),
        blob: vi.fn().mockResolvedValue(new Blob()),
      });
    });
  });

  // -------------------------------------------------------------------------
  // Verify flow — error states
  // -------------------------------------------------------------------------
  describe("verify flow — error states", () => {
    async function setupFiles(user: ReturnType<typeof userEvent.setup>) {
      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;
      await user.upload(imageInput, makeJpeg());
      await user.upload(pdfInput, makePdf());
    }

    it("shows an error message when fetch returns a non-ok HTTP status", async () => {
      global.fetch = mockFetchError(422);
      const user = userEvent.setup();
      render(<ChatLandingPage />);
      await setupFiles(user);

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert.textContent).toMatch(/http 422/i);
      });
    });

    it("shows an error when the response shape is unexpected", async () => {
      global.fetch = mockFetchOk({ unexpected: "format" });
      const user = userEvent.setup();
      render(<ChatLandingPage />);
      await setupFiles(user);

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert.textContent).toMatch(/unexpected response format/i);
      });
    });

    it("shows an error when the network call fails entirely", async () => {
      global.fetch = mockFetchNetworkFailure();
      const user = userEvent.setup();
      render(<ChatLandingPage />);
      await setupFiles(user);

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });

    it("does not show a results panel when the verify call fails", async () => {
      global.fetch = mockFetchError(500);
      const user = userEvent.setup();
      render(<ChatLandingPage />);
      await setupFiles(user);

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(
        screen.queryByRole("heading", { name: /verification results/i }),
      ).not.toBeInTheDocument();
    });

    it("re-enables the verify button after a failed request", async () => {
      global.fetch = mockFetchError(503);
      const user = userEvent.setup();
      render(<ChatLandingPage />);
      await setupFiles(user);

      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(
        screen.getByRole("button", { name: /start verifying labels/i }),
      ).toBeEnabled();
    });
  });

  // -------------------------------------------------------------------------
  // CSV download
  // -------------------------------------------------------------------------
  describe("CSV download", () => {
    async function renderWithResults(): Promise<ReturnType<typeof userEvent.setup>> {
      global.fetch = mockFetchOk({
        brand_match: "yes",
        alcohol_match: "yes",
        warning_match: "yes",
      });
      const user = userEvent.setup();
      render(<ChatLandingPage />);

      const imageInput = document.querySelector(
        'input[accept=".jpeg,.jpg,image/jpeg"]',
      ) as HTMLInputElement;
      const pdfInput = document.querySelector(
        'input[accept=".pdf,application/pdf"]',
      ) as HTMLInputElement;

      await user.upload(imageInput, makeJpeg());
      await user.upload(pdfInput, makePdf());
      await user.click(
        screen.getByRole("button", { name: /start verifying labels/i }),
      );

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /verification results/i }),
        ).toBeInTheDocument();
      });

      return user;
    }

    it("calls fetch with /export when Download CSV is clicked", async () => {
      // After verify, swap fetch to a CSV-returning mock
      const user = await renderWithResults();

      // Spy on createObjectURL before setting up the export mock
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: vi.fn().mockResolvedValue(new Blob(["a,b,c"], { type: "text/csv" })),
        json: vi.fn().mockResolvedValue({}),
      });

      await user.click(screen.getByRole("button", { name: /download csv/i }));

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          "http://localhost:8000/export",
        );
      });
    });

    it("creates an object URL and triggers an anchor download", async () => {
      const user = await renderWithResults();

      const createObjectUrlSpy = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:mock-url");
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

      // Capture the anchor click instead of actually navigating
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: vi.fn().mockResolvedValue(new Blob(["a,b,c"], { type: "text/csv" })),
        json: vi.fn().mockResolvedValue({}),
      });

      await user.click(screen.getByRole("button", { name: /download csv/i }));

      await waitFor(() => {
        expect(createObjectUrlSpy).toHaveBeenCalled();
        expect(clickSpy).toHaveBeenCalled();
      });
    });

    it("shows an error if the export fetch fails", async () => {
      const user = await renderWithResults();

      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        blob: vi.fn().mockResolvedValue(new Blob()),
        json: vi.fn().mockResolvedValue({}),
      });

      await user.click(screen.getByRole("button", { name: /download csv/i }));

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toBeInTheDocument();
        expect(alert.textContent).toMatch(/export failed/i);
      });
    });

    it("shows an error if the export fetch throws a network error", async () => {
      const user = await renderWithResults();

      global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

      await user.click(screen.getByRole("button", { name: /download csv/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });
  });
});
