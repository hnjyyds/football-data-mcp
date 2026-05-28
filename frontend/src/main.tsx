import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary } from "./components/system/ErrorBoundary";
import { installGlobalErrorReporter, reportError } from "./errorReporter";
import "./index.css";

installGlobalErrorReporter();

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary onError={(err, info) => reportError(err, { kind: "react-render", componentStack: info.componentStack ?? null })}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
