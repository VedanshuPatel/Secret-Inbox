import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import App from "./App";
import { jsonResponse, stubFetch } from "./test/helpers";

describe("application entry and login", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("shows the landing page", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Say it like you mean it." })).toBeTruthy();
    expect(screen.getByLabelText("Username")).toBeTruthy();
  });

  it("sends the entered username to the authentication API", async () => {
    const fetchMock = stubFetch((input) => Promise.resolve(
      String(input).includes(":8001/auth")
        ? jsonResponse({ id: "user-1", username: "Mira" })
        : String(input).includes(":8001/users/")
          ? jsonResponse({ username: "Mira", accepting_messages: true })
          : jsonResponse([]),
    ));
    render(<App />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "Mira" } });
    fireEvent.click(screen.getByRole("button", { name: /Open my inbox/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/auth",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "Mira" }),
      }),
    ));
  });

  it("persists the returned user id after authentication", async () => {
    stubFetch((input) => Promise.resolve(
      String(input).includes(":8001/auth")
        ? jsonResponse({ id: "user-1", username: "Mira" })
        : String(input).includes(":8001/users/")
          ? jsonResponse({ username: "Mira", accepting_messages: true })
          : jsonResponse([]),
    ));
    render(<App />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "Mira" } });
    fireEvent.click(screen.getByRole("button", { name: /Open my inbox/ }));

    await waitFor(() => expect(localStorage.getItem("userId")).toBe("user-1"));
  });

  it("shows the authentication service's login error", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ detail: "Username cannot be blank." }, 400)));
    render(<App />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: /Open my inbox/ }));

    expect((await screen.findByRole("alert")).textContent).toContain("Username cannot be blank.");
  });

  it("does not persist a session after a rejected login", async () => {
    stubFetch(() => Promise.resolve(jsonResponse({ detail: "Username cannot be blank." }, 400)));
    render(<App />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: /Open my inbox/ }));
    await screen.findByRole("alert");

    expect(localStorage.getItem("userId")).toBeNull();
  });

  it("renders the public feedback route from its shared invite token", () => {
    window.history.replaceState({}, "", "/?route=feedback&invite=shared-invite-token");
    render(<App />);

    expect(screen.getByRole("heading", { name: "Send a little honesty." })).toBeTruthy();
  });

  it("shows an error when the feedback link has no invite token", () => {
    window.history.replaceState({}, "", "/?route=feedback");
    render(<App />);

    expect(screen.getByRole("alert").textContent).toContain("invite link is missing or invalid");
  });

  it("renders the private check route from its query parameters", async () => {
    window.history.replaceState({}, "", "/?route=check&token=private-token");
    stubFetch(() => Promise.resolve(jsonResponse({
      content: "Hello",
      category: null,
      reply: null,
      reply_at: null,
      reaction: null,
      created_at: "2026-10-12T12:00:00Z",
    })));
    render(<App />);

    expect(await screen.findByText("Hello")).toBeTruthy();
  });

  it("restores the dashboard when a session is present", async () => {
    localStorage.setItem("userId", "user-1");
    stubFetch((input) => Promise.resolve(
      String(input).includes(":8001/")
        ? jsonResponse({ username: "Mira", accepting_messages: true })
        : jsonResponse([]),
    ));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome, Mira" })).toBeTruthy();
  });

  it("clears the session when logging out", async () => {
    localStorage.setItem("userId", "user-1");
    stubFetch((input) => Promise.resolve(
      String(input).includes(":8001/")
        ? jsonResponse({ username: "Mira", accepting_messages: true })
        : jsonResponse([]),
    ));
    render(<App />);
    await screen.findByRole("heading", { name: "Welcome, Mira" });

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(localStorage.getItem("userId")).toBeNull();
    expect(await screen.findByRole("heading", { name: "Say it like you mean it." })).toBeTruthy();
  });
});
