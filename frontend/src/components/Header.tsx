import { BookOpen, Github, Moon, ShieldCheck, Sun } from "lucide-react";

import type { ModelStatus } from "../lib/api/types";

interface HeaderProps {
  status: ModelStatus | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function Header({ status, theme, onToggleTheme }: HeaderProps) {
  const ready = status?.mode === "local_review";
  return (
    <header className="site-header">
      <a className="brand" href="#main-content" aria-label="WoundScope 首頁">
        <span className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>
          <strong>WoundScope</strong>
          <small>傷口分割複核工作台</small>
        </span>
      </a>

      <div className="header-actions">
        <span className={`status-chip ${ready ? "is-ready" : "is-showcase"}`}>
          <ShieldCheck size={18} aria-hidden="true" />
          {ready ? "Local model ready" : "Code-only showcase"}
        </span>
        <nav aria-label="專案導覽">
          <a href="/MODEL_CARD.md">
            <BookOpen size={18} aria-hidden="true" />
            <span>Model Card</span>
          </a>
          <a href="https://github.com/kuotunyu/WoundScope">
            <Github size={18} aria-hidden="true" />
            <span>GitHub</span>
          </a>
        </nav>
        <button
          className="icon-button theme-toggle"
          type="button"
          onClick={onToggleTheme}
          aria-label={theme === "light" ? "切換深色模式" : "切換淺色模式"}
        >
          {theme === "light" ? (
            <Moon size={20} aria-hidden="true" />
          ) : (
            <Sun size={20} aria-hidden="true" />
          )}
        </button>
      </div>
    </header>
  );
}
