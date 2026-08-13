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

it("frames the showcase as a scientific workbench instead of an editorial headline", async () => {
  mockStatus();
  const { container } = render(<App />);
  await screen.findByText("研究展示模式");

  expect(screen.getByText("Code-only 展示")).toBeVisible();
  expect(
    screen.getByRole("heading", {
      level: 1,
      name: "WoundScope 傷口分割複核工作台",
    }),
  ).toBeVisible();
  expect(screen.queryByText(/從像素預測/)).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toBeVisible();
  expect(screen.getByText("Medical Computer Vision")).toBeVisible();
  expect(screen.getByText("目前工作區")).toBeVisible();
  expect(screen.getByRole("heading", { level: 2, name: "已驗證證據" })).toBeVisible();
  expect(screen.queryByText("Verified evidence")).not.toBeInTheDocument();
  expect(screen.queryByText("Current workspace")).not.toBeInTheDocument();

  const provenance = screen.getByRole("region", {
    name: "Artifact 與研究來源",
  });
  expect(within(provenance).getAllByRole("term")).toHaveLength(4);
  expect(screen.queryByText(/每個結果/)).not.toBeInTheDocument();
  expect(container.querySelectorAll(".provenance-grid article")).toHaveLength(0);
});

it("explains how to move from code-only showcase to local review", async () => {
  mockStatus();
  render(<App />);
  await screen.findByText("研究展示模式");

  const guide = screen.getByRole("region", { name: "使用流程" });
  expect(within(guide).getByRole("list")).toBeVisible();
  expect(within(guide).getByText("準備 artifacts")).toBeVisible();
  expect(within(guide).getByText("啟動本機工作台")).toBeVisible();
  expect(within(guide).getByText("上傳並複核")).toBeVisible();
  expect(within(guide).getByRole("link", { name: "查看本機啟用方式" })).toHaveAttribute(
    "href",
    "https://github.com/kuotunyu/WoundScope#啟動分割複核工作台",
  );
  expect(screen.queryByLabelText("選擇傷口影像")).not.toBeInTheDocument();
  expect(screen.queryByText("立即推論")).not.toBeInTheDocument();
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

  expect(await screen.findByLabelText("選擇傷口影像")).toBeVisible();
  expect(
    screen.getByRole("heading", {
      level: 1,
      name: "WoundScope 傷口分割複核工作台",
    }),
  ).toBeVisible();
  expect(screen.queryByText("本機複核 · Private Runtime")).not.toBeInTheDocument();
  expect(screen.queryByText("研究展示模式")).not.toBeInTheDocument();
});
