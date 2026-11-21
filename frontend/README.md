# Akshaya-Access — judge-facing live call view

Vite + React + TypeScript single page. It polls the backend (`GET /calls`, `GET /calls/{id}`, every 1 s) and shows
the call as it happens: call list, live Malayalam transcript (with English below), step tracker, bill card,
payment card and handoff banner. Built only against `../contracts/tools-api.yaml`.

## Install

```
npm install
```

## Run

```
npm run dev          # http://localhost:5173
```

The backend URL comes from `VITE_BACKEND_URL` (default `http://localhost:8000`; copy `.env.example` to `.env` to change it).
The backend must allow CORS from `http://localhost:5173`.

If the backend is unreachable a red banner appears and polling keeps retrying.

## Mock mode (no backend)

```
VITE_USE_MOCK=1 npm run dev
```

Serves one scripted call (Rajan K, ₹640, values from `contracts/fixtures/bills.json`, copied to `src/mock/bills.json`).
It plays automatically (~20 s) up to a pending SIMULATED UPI 123PAY payment; click **Bank confirms** or **Bank declines**
in the demo controls to finish it. Reload the page to replay.

## Demo notes

- A purple **SIMULATED** badge shows whenever the bill or payment has `simulated: true`.
- The "Bank confirms / Bank declines" buttons only appear while payment status is `pending`; they call
  `POST /simulator/payments/{id}/complete` and are labelled as demo controls.
- The newest active call is selected automatically; click another call to pin it, and use
  "Follow newest active call" to go back.
- Malayalam renders with Noto Sans Malayalam, bundled via `@fontsource/noto-sans-malayalam` (works offline on the projector laptop).

## Test / build

```
npx vitest run       # step-tracker mapping, SIMULATED badge logic, mock call script
npm run build        # tsc --noEmit + vite build
```
