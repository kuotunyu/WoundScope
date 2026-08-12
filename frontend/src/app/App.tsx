import { useEffect, useState } from "react";

import { EvidenceStrip } from "../components/EvidenceStrip";
import { Header } from "../components/Header";
import { ProvenancePanel } from "../components/ProvenancePanel";
import { ResearchShowcase } from "../components/ResearchShowcase";
import { SafetyFooter } from "../components/SafetyFooter";
import { ReviewWorkspace } from "../features/review/ReviewWorkspace";
import { ApiError, fetchModelStatus } from "../lib/api/client";
import type { ModelStatus } from "../lib/api/types";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  return window.localStorage.getItem("woundscope-theme") === "dark" ? "dark" : "light";
}

export function App() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("woundscope-theme", theme);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "light" ? "#f4f1ea" : "#172024");
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();
    fetchModelStatus(controller.signal)
      .then((modelStatus) => {
        setStatus(modelStatus);
        setStatusError(false);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (error instanceof ApiError) {
          setStatusError(true);
        }
      });
    return () => controller.abort();
  }, []);

  function toggleTheme() {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要內容
      </a>
      <Header status={status} theme={theme} onToggleTheme={toggleTheme} />
      <main id="main-content" tabIndex={-1}>
        {status?.mode === "local_review" && status.model_available ? (
          <ReviewWorkspace status={status} />
        ) : (
          <ResearchShowcase status={status} statusError={statusError} />
        )}
        <EvidenceStrip />
        <ProvenancePanel status={status} />
      </main>
      <SafetyFooter />
    </div>
  );
}
