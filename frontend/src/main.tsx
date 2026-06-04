import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary } from "./components/system/ErrorBoundary";
import { installGlobalErrorReporter, reportError } from "./errorReporter";
import MobilePwaPage from "./pages/MobilePwaPage";
import "./index.css";

installGlobalErrorReporter();

const isMobilePwaRoute = window.location.pathname === "/mobile" || window.location.pathname.startsWith("/mobile/");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      reportError(error, { kind: "service-worker-register" });
    });
  });
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary onError={(err, info) => reportError(err, { kind: "react-render", componentStack: info.componentStack ?? null })}>
      {isMobilePwaRoute ? <MobilePwaPage /> : <App />}
    </ErrorBoundary>
  </React.StrictMode>
);
