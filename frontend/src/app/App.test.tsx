import { render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";

import { App } from "./App";

const showcaseStatus = {
  mode: "showcase",
  model_available: false,
  calibration_available: false,
  model_label: "EfficientNet-B0 U-Net / ONNX",
  model_sha256_prefix: null,
  provider: "unavailable",
  message: "目前為研究展示模式；本機模型可用時才開啟分割複核。",
};

function mockStatus(payload = showcaseStatus) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

it("renders verified evidence in permission-aware showcase mode", async () => {
  mockStatus();

  render(<App />);

  expect(await screen.findByText("研究展示模式")).toBeVisible();
  expect(screen.getByText("0.8508")).toBeVisible();
  expect(screen.getByText(/Official Validation · 200 張/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "開始分割複核" })).not.toBeInTheDocument();
  expect(screen.getByText(/非臨床診斷/)).toBeVisible();
  expect(screen.getByRole("link", { name: "跳到主要內容" })).toHaveAttribute(
    "href",
    "#main-content",
  );
  expect(screen.getByRole("link", { name: "在 GitHub 查看 WoundScope" })).toBeVisible();
});

it("has no automated accessibility violations in showcase mode", async () => {
  mockStatus();
  const { container } = render(<App />);
  await screen.findByText("研究展示模式");

  const results = await axe.run(container);

  expect(results.violations).toHaveLength(0);
});

it("keeps interface framing zh-TW first with semantic evidence and provenance", async () => {
  mockStatus();
  const { container } = render(<App />);
  await screen.findByText("研究展示模式");

  expect(screen.getByText("Code-only 展示")).toBeVisible();
  expect(screen.getByText("Medical Computer Vision · 研究原型")).toBeVisible();
  expect(screen.getByText("目前工作區")).toBeVisible();
  expect(screen.getByRole("heading", { level: 2, name: "已驗證證據" })).toBeVisible();
  expect(screen.getByText("證據，不是裝飾")).toBeVisible();
  expect(screen.queryByText("Verified evidence")).not.toBeInTheDocument();
  expect(screen.queryByText("Current workspace")).not.toBeInTheDocument();

  const provenance = screen.getByRole("region", {
    name: "每個結果，都必須知道從哪裡來。",
  });
  expect(within(provenance).getAllByRole("term")).toHaveLength(4);
  expect(container.querySelectorAll(".provenance-grid article")).toHaveLength(0);
});

it("offers a labeled theme control without a network font dependency", async () => {
  mockStatus();
  render(<App />);
  await screen.findByText("研究展示模式");

  expect(screen.getByRole("button", { name: "切換深色模式" })).toBeVisible();
  expect(document.querySelector('link[href*="fonts.googleapis.com"]')).toBeNull();
});

it("renders a safe status error when readiness cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  render(<App />);

  await waitFor(() => {
    expect(screen.getByText("無法取得本機模型狀態")).toBeVisible();
  });
  expect(screen.queryByText("offline")).not.toBeInTheDocument();
});

it("opens the review workspace only when a local model is ready", async () => {
  mockStatus({
    ...showcaseStatus,
    mode: "local_review",
    model_available: true,
    calibration_available: true,
    provider: "CPUExecutionProvider",
    message: "本機模型已就緒。",
  });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "傷口分割複核工作台" })).toBeVisible();
  expect(screen.getByLabelText("選擇傷口影像")).toBeVisible();
  expect(screen.queryByText("研究展示模式")).not.toBeInTheDocument();
});
