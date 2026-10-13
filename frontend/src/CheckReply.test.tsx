import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CheckReply from "./CheckReply";
import { jsonResponse, stubFetch } from "./test/helpers";

const sentMessage = {
  content: "A thoughtful note.",
  category: "Compliment",
  reply: null,
  reply_at: null,
  reaction: null,
  created_at: "2026-10-12T12:00:00Z",
};

describe("private reply-check page", () => {
  it("shows loading state while the private message is fetched", () => {
    stubFetch(() => new Promise(() => {}));
    render(<CheckReply token="secret-token" />);

    expect(screen.getByRole("status").textContent).toContain("Looking for your message");
  });

  it("renders fetched message content", async () => {
    stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    render(<CheckReply token="secret-token" />);

    expect(await screen.findByText("A thoughtful note.")).toBeTruthy();
  });

  it("renders the message category when present", async () => {
    stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    render(<CheckReply token="secret-token" />);

    expect(await screen.findByText("Compliment")).toBeTruthy();
  });

  it("shows written-reply waiting state when no reply exists", async () => {
    stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    render(<CheckReply token="secret-token" />);

    expect(await screen.findByText("Waiting for a written reply")).toBeTruthy();
  });

  it("shows and copies the private reply-check link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    render(<CheckReply token="secret-token" />);

    const checkUrl = `${window.location.origin}/?route=check&token=secret-token`;
    expect((screen.getByLabelText("Private reply-check link") as HTMLInputElement).value).toBe(checkUrl);
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(checkUrl));
    expect(await screen.findByRole("button", { name: "Copied!" })).toBeTruthy();
  });

  it("shows sender-facing reaction when one exists", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ ...sentMessage, reaction: "❤️" })));
    render(<CheckReply token="secret-token" />);

    expect((await screen.findByText(/They reacted/)).textContent).toContain("❤️");
  });

  it("shows the owner's written reply when one exists", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ ...sentMessage, reply: "Thank you for sharing this!" })));
    render(<CheckReply token="secret-token" />);

    expect(await screen.findByText("Thank you for sharing this!")).toBeTruthy();
  });

  it("shows an invalid-link message when the token is not found", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ detail: "No message found." }, 404)));
    render(<CheckReply token="missing-token" />);

    expect((await screen.findByRole("alert")).textContent).toContain("This link is no longer valid");
  });

  it("polls for updated message state every five seconds", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    render(<CheckReply token="secret-token" />);
    await act(async () => { await Promise.resolve(); });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders a reaction that arrives during polling", async () => {
    vi.useFakeTimers();
    let requestCount = 0;
    stubFetch(() => {
      requestCount += 1;
      return Promise.resolve(jsonResponse(
        requestCount === 1 ? sentMessage : { ...sentMessage, reaction: "🔥" },
      ));
    });
    render(<CheckReply token="secret-token" />);
    await act(async () => { await Promise.resolve(); });

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });

    expect(screen.getByText(/They reacted/).textContent).toContain("🔥");
  });

  it("stops polling after unmount", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(() => Promise.resolve(jsonResponse(sentMessage)));
    const { unmount } = render(<CheckReply token="secret-token" />);
    await act(async () => { await Promise.resolve(); });
    unmount();

    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
