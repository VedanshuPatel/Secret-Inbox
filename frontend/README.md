# Frontend

The Secret Inbox browser client is a React 19 and TypeScript single-page
application bundled by Vite. Tailwind CSS 4 is integrated with the Vite plugin.
The client expects the user API at `http://localhost:8001`, the message API at
`http://localhost:8002`, and the Vite site at `http://localhost:5173`.

For complete system setup, backend APIs, data flow, and safety limitations,
see the [project README](../README.md).

## Routes

The app selects its screen from the current URL query parameters:

| URL | Screen |
| --- | --- |
| `/` | Login/registration, or the inbox dashboard for the saved `userId` |
| `/?route=feedback&invite=<invite-token>` | Anonymous feedback form for a shared invite |
| `/?route=check&token=<reply-token>` | Sender's private message and reply/reaction status |

The signed-in user ID is stored in browser `localStorage` under `userId`.
Logging out clears local storage. The client uses the existing APIs; it does
not provide authentication by itself.

## Main UI modules

- `src/App.tsx` handles URL-based screen selection, login, and session state.
- `src/Dashboard.tsx` loads the owner's settings and inbox and provides
  message-management actions, including creating a shared invite link,
  copying it, and opening a prefilled Outlook draft.
- `src/Feedback.tsx` submits anonymous notes and presents the sender's private
  follow-up link.
- `src/CheckReply.tsx` polls the message API for a reaction or written reply.
- `src/index.css` contains Tailwind theme tokens and global page styles.

## Commands

Run these commands from this directory:

```sh
npm ci
npm run dev -- --host 127.0.0.1
npm test
npm run build
npm run lint
```

`npm test` runs Vitest in jsdom with React Testing Library. The tests mock
`fetch`, so they do not need the backend services. They cover route selection,
login, feedback submission, reply polling, inbox controls, and message actions.

## Styling and API conventions

The interface uses Tailwind utility classes and shared color/font tokens in
`src/index.css`. Keep interactive controls keyboard-operable and preserve
accessible labels and pressed/checked states when changing component markup.

The API origins are currently hard-coded in the UI components. If deployment
configuration is added later, update the origin in every affected screen and
its tests together. Request and response shapes are documented in the
[project API overview](../README.md#api-overview).
