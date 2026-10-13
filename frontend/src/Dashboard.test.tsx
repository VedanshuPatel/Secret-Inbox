import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard";
import { jsonResponse, stubFetch } from "./test/helpers";

const messages = [
  {
    id: 1,
    content: "Your kindness makes a difference.",
    status: "active" as const,
    category: "Compliment",
    reaction: null,
    reply: null,
    reply_at: null,
    report_reason: null,
    created_at: "2026-10-12T12:00:00Z",
  },
];

function setupDashboard(actionHandler?: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>) {
  const fetchMock = stubFetch((input, init) => {
    const url = String(input);
    if (url.includes(":8001/users/")) {
      return Promise.resolve(jsonResponse({ username: "Mira", accepting_messages: true }));
    }
    if (url.includes(":8002/invites/")) {
      return Promise.resolve(jsonResponse({ invite_token: "shared-invite-token" }, 201));
    }
    if (url.includes(":8002/messages/mira?status=")) {
      return Promise.resolve(jsonResponse(messages));
    }
    return actionHandler?.(input, init) ?? Promise.resolve(jsonResponse({ ...messages[0], reaction: "❤️" }));
  });
  const onLogout = vi.fn();
  render(<Dashboard userId="mira" onLogout={onLogout} />);
  return { fetchMock, onLogout };
}

describe("inbox dashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("loads owner details", async () => {
    setupDashboard();

    expect(await screen.findByRole("heading", { name: "Welcome, Mira" })).toBeTruthy();
  });

  it("loads active inbox messages", async () => {
    setupDashboard();

    expect(await screen.findByText("Your kindness makes a difference.")).toBeTruthy();
  });

  it("shows an empty-state message when the inbox is empty", async () => {
    stubFetch((input) => Promise.resolve(String(input).includes(":8001/")
      ? jsonResponse({ username: "Mira", accepting_messages: true })
      : jsonResponse([])));
    render(<Dashboard userId="mira" onLogout={vi.fn()} />);

    expect(await screen.findByText("Your inbox is waiting")).toBeTruthy();
    expect(screen.getByText("Create a shared invite and send it to anyone you want to hear from.")).toBeTruthy();
  });

  it("logs out through the supplied callback", async () => {
    const { onLogout } = setupDashboard();
    await screen.findByRole("heading", { name: "Welcome, Mira" });
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(onLogout).toHaveBeenCalledOnce();
  });

  it("switches the selected message tab", async () => {
    setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "Archived" }));

    expect(screen.getByRole("heading", { name: "Archived (1)" })).toBeTruthy();
  });

  it("requests messages for the selected tab", async () => {
    const { fetchMock } = setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "Archived" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/mira?status=archived"));
  });

  it("creates and copies a shared invite link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const { fetchMock } = setupDashboard();
    await screen.findByRole("heading", { name: "Welcome, Mira" });
    fireEvent.click(screen.getByRole("button", { name: "Generate invite link" }));
    await screen.findByDisplayValue(`${window.location.origin}/?route=feedback&invite=shared-invite-token`);
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      `${window.location.origin}/?route=feedback&invite=shared-invite-token`,
    ));
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/invites/mira", expect.objectContaining({
      method: "POST",
    }));
    expect(await screen.findByRole("button", { name: "Copied!" })).toBeTruthy();
  });

  it("opens a shared email draft using the same invite link", async () => {
    setupDashboard();
    await screen.findByRole("heading", { name: "Welcome, Mira" });
    fireEvent.click(screen.getByRole("button", { name: "Generate invite link" }));

    const draft = await screen.findByRole("link", { name: "Email with Outlook" });
    const parsedDraft = new URL(draft.getAttribute("href") ?? "");
    expect(parsedDraft.searchParams.get("body")).toContain("invite=shared-invite-token");
    expect(parsedDraft.searchParams.get("body")).toContain("The form doesn't ask for your name");
    expect(parsedDraft.searchParams.get("subject")).toBe("Could you share some honest feedback?");
  });

  it("shows paused state when inbox accepting is switched off", async () => {
    setupDashboard();
    await screen.findByRole("heading", { name: "Welcome, Mira" });
    const toggle = screen.getByRole("switch", { name: "Accept new messages" });
    fireEvent.click(toggle);

    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("Your inbox is paused")).toBeTruthy();
  });

  it("saves inbox acceptance setting through the settings API", async () => {
    const { fetchMock } = setupDashboard();
    await screen.findByRole("heading", { name: "Welcome, Mira" });
    fireEvent.click(screen.getByRole("switch", { name: "Accept new messages" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/users/mira/settings",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ accepting_messages: false }) }),
    ));
  });

  it("saves and highlights a selected reaction", async () => {
    const { fetchMock } = setupDashboard((input) => {
      if (String(input).includes("/reaction")) {
        return Promise.resolve(jsonResponse({ ...messages[0], reaction: "😂" }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "React with 😂" }));

    const selected = await screen.findByRole("button", { name: "React with 😂" });
    await waitFor(() => expect(selected.getAttribute("aria-pressed")).toBe("true"));
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8002/messages/1/reaction",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ reaction: "😂" }) }),
    );
  });

  it("reverts a failed reaction and explains the error", async () => {
    setupDashboard((input) => String(input).includes("/reaction")
      ? Promise.resolve(jsonResponse({ detail: "Message not found." }, 404))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "React with ❤️" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Message not found.");
    expect(screen.getByRole("button", { name: "React with ❤️" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("times out a reaction save and restores its previous selection", async () => {
    setupDashboard((input) => String(input).includes("/reaction")
      ? Promise.reject(new DOMException("The operation timed out.", "TimeoutError"))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "React with ❤️" }));

    expect((await screen.findByRole("alert")).textContent).toContain("took too long");
    expect(screen.getByRole("button", { name: "React with ❤️" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("submits a written reply", async () => {
    setupDashboard((input) => String(input).includes("/reply")
      ? Promise.resolve(jsonResponse({ ...messages[0], reply: "Thank you!" }))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "💬 Reply" }));
    fireEvent.change(screen.getByPlaceholderText("Write a reply..."), { target: { value: "Thank you!" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));

    expect(await screen.findByText("Thank you!")).toBeTruthy();
    expect(screen.getByText("Your reply")).toBeTruthy();
  });

  it("requests and displays an AI reply suggestion", async () => {
    const { fetchMock } = setupDashboard((input) => String(input).includes("/suggest-reply")
      ? Promise.resolve(jsonResponse({ suggestion: "Thanks for saying that!" }))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Suggest Reply/ }));

    expect(await screen.findByDisplayValue("Thanks for saying that!")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/1/suggest-reply", { method: "POST" });
  });

  it("shows AI suggestion failures", async () => {
    setupDashboard((input) => String(input).includes("/suggest-reply")
      ? Promise.resolve(jsonResponse({ detail: "AI service is unavailable." }, 503))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Suggest Reply/ }));

    expect(await screen.findByText(/AI service is unavailable/)).toBeTruthy();
  });

  it("displays the generated inbox summary", async () => {
    const { fetchMock } = setupDashboard((input) => String(input).includes("/summarize")
      ? Promise.resolve(jsonResponse({ summary: "People appreciate your kindness." }))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Summarize Inbox/ }));

    expect(await screen.findByText("People appreciate your kindness.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/mira/summarize", { method: "POST" });
  });

  it("dismisses the inbox summary", async () => {
    setupDashboard((input) => String(input).includes("/summarize")
      ? Promise.resolve(jsonResponse({ summary: "People appreciate your kindness." }))
      : Promise.resolve(jsonResponse({})));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Summarize Inbox/ }));
    await screen.findByText("People appreciate your kindness.");

    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    expect(screen.queryByText("People appreciate your kindness.")).toBeNull();
  });

  it("archives a message", async () => {
    const { fetchMock } = setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "🗄️ Archive" }));

    await waitFor(() => expect(screen.queryByText("Your kindness makes a difference.")).toBeNull());
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/1/archive", { method: "PATCH" });
  });

  it("restores an archived message", async () => {
    const { fetchMock } = setupDashboard((input) => String(input).includes("status=archived")
      ? Promise.resolve(jsonResponse([{ ...messages[0], status: "archived" }]))
      : Promise.resolve(jsonResponse({ ...messages[0], status: "active" })));
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "Archived" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Move to Inbox/ })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Move to Inbox/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/1/restore", { method: "PATCH" }));
    expect(screen.queryByText("Your kindness makes a difference.")).toBeNull();
  });

  it("submits a report reason for the selected message", async () => {
    const { fetchMock } = setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "🚩 Report" }));
    fireEvent.change(screen.getByPlaceholderText("Reason for reporting (optional)"), { target: { value: "Spam" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm report" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8002/messages/1/report",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ reason: "Spam" }) }),
    ));
  });

  it("removes a message from the current view after reporting", async () => {
    setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: "🚩 Report" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm report" }));

    await waitFor(() => expect(screen.queryByText("Your kindness makes a difference.")).toBeNull());
  });

  it("deletes only after confirmation", async () => {
    const { fetchMock } = setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Delete/ }));

    expect(window.confirm).toHaveBeenCalledWith("Permanently delete this message?");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("http://localhost:8002/messages/1", { method: "DELETE" }));
    expect(screen.queryByText("Your kindness makes a difference.")).toBeNull();
  });

  it("does not delete when confirmation is declined", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const { fetchMock } = setupDashboard();
    await screen.findByText("Your kindness makes a difference.");
    fireEvent.click(screen.getByRole("button", { name: /Delete/ }));

    expect(fetchMock).not.toHaveBeenCalledWith("http://localhost:8002/messages/1", { method: "DELETE" });
    expect(screen.getByText("Your kindness makes a difference.")).toBeTruthy();
  });
});
