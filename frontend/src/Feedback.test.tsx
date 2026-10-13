import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Feedback from "./Feedback";
import { jsonResponse, stubFetch } from "./test/helpers";

describe("anonymous feedback form", () => {
  it("submits the message and selected category", async () => {
    const fetchMock = stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "reply-123" }, 201)));
    render(<Feedback inviteToken="invite-123" />);

    fireEvent.click(screen.getByRole("button", { name: "Compliment" }));
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "You made my day." } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8002/messages/invite/invite-123",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ content: "You made my day.", category: "Compliment" }),
      }),
    );
    expect(await screen.findByRole("heading", { name: "Your note is on its way." })).toBeTruthy();
  });

  it("shows the generated private reply-check link", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "reply-123" }, 201)));
    render(<Feedback inviteToken="invite-123" />);
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "You made my day." } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));

    await screen.findByRole("heading", { name: "Your note is on its way." });
    expect((screen.getByLabelText("Private reply-check link") as HTMLInputElement).value)
      .toBe(`${window.location.origin}/?route=check&token=reply-123`);
  });

  it("provides a direct link to check for a reply and retains the copyable link", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "reply-123" }, 201)));
    render(<Feedback inviteToken="invite-123" />);
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "A note" } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));

    const checkUrl = `${window.location.origin}/?route=check&token=reply-123`;
    const replyLink = await screen.findByRole("link", { name: "Check for a reply" });

    expect(replyLink.getAttribute("href")).toBe(checkUrl);
    expect((screen.getByLabelText("Private reply-check link") as HTMLInputElement).value).toBe(checkUrl);
    expect(screen.getByRole("button", { name: "Copy link" })).toBeTruthy();
  });

  it("selects a feedback category", () => {
    stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "unused" })));
    render(<Feedback inviteToken="invite-123" />);
    const category = screen.getByRole("button", { name: "Advice" });

    fireEvent.click(category);
    expect(category.getAttribute("aria-pressed")).toBe("true");
  });

  it("clears a category when its selected option is clicked again", () => {
    stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "unused" })));
    render(<Feedback inviteToken="invite-123" />);
    const category = screen.getByRole("button", { name: "Advice" });
    fireEvent.click(category);
    fireEvent.click(category);

    expect(category.getAttribute("aria-pressed")).toBe("false");
  });

  it("shows API errors and keeps the form available after a rejected submission", async () => {
    const fetchMock = stubFetch(() => Promise.resolve(jsonResponse({ detail: "This inbox is paused." }, 400)));
    render(<Feedback inviteToken="invite-123" />);
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "A note" } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));

    expect((await screen.findByRole("alert")).textContent).toContain("This inbox is paused.");
    expect(screen.getByRole("button", { name: "Send anonymously" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports network errors without falsely showing success", async () => {
    stubFetch(() => Promise.reject(new Error("Network unavailable")));
    render(<Feedback inviteToken="invite-123" />);
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "A note" } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Network unavailable");
    expect(screen.queryByRole("heading", { name: "Your note is on its way." })).toBeNull();
  });

  it("copies the generated check link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    stubFetch(() => Promise.resolve(jsonResponse({ reply_token: "reply-123" }, 201)));
    render(<Feedback inviteToken="invite-123" />);
    fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "A note" } });
    fireEvent.click(screen.getByRole("button", { name: "Send anonymously" }));
    await screen.findByRole("button", { name: "Copy link" });
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      `${window.location.origin}/?route=check&token=reply-123`,
    ));
    expect(await screen.findByRole("button", { name: "Copied!" })).toBeTruthy();
  });
});
