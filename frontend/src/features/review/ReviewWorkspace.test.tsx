import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ModelStatus, PredictionResponse } from "../../lib/api/types";
import { ReviewWorkspace } from "./ReviewWorkspace";

const { predictSpy } = vi.hoisted(() => ({ predictSpy: vi.fn() }));

vi.mock("../../lib/api/client", () => ({
  ApiError: class ApiError extends Error {
    code: string;
    status: number;

    constructor(code: string, message: string, status: number) {
      super(message);
      this.code = code;
      this.status = status;
    }
  },
  predictImage: predictSpy,
}));

const readyStatus: ModelStatus = {
  mode: "local_review",
  model_available: true,
  calibration_available: true,
  model_label: "Synthetic ONNX",
  model_sha256_prefix: "abc123def456",
  provider: "CPUExecutionProvider",
  message: "本機模型已就緒。",
};

const result: PredictionResponse = {
  overlay_data_url: "data:image/png;base64,b3ZlcmxheQ==",
  mask_data_url: "data:image/png;base64,bWFzaw==",
  wound_pixel_ratio: 0.238,
  confidence_score: 0.82,
  confidence_label: "模型分割信心，非臨床信心",
  inference_ms: 12,
  low_confidence: true,
  review_reasons: ["confidence_below_dev_cutoff"],
  provider: "CPUExecutionProvider",
};

function syntheticPngFile(name = "synthetic.png") {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: "image/png" });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  predictSpy.mockReset();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:woundscope-preview"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
});

it("uploads only after explicit action and renders nonclinical results", async () => {
  predictSpy.mockResolvedValue(result);
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);

  await user.upload(screen.getByLabelText("選擇傷口影像"), syntheticPngFile());
  expect(screen.getByLabelText("選擇傷口影像")).toHaveAttribute("name", "review-image");
  expect(screen.getByLabelText("選擇傷口影像")).toHaveAttribute("autocomplete", "off");
  expect(predictSpy).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));

  expect(await screen.findByText("模型分割信心，非臨床信心")).toBeVisible();
  expect(screen.getByRole("heading", { level: 2, name: "需要人工複核" })).toBeVisible();
  expect(screen.getByText("23.8%")).toBeVisible();
});

it("limits live announcements and keeps local-review framing zh-TW first", () => {
  const { container } = render(<ReviewWorkspace status={readyStatus} />);

  expect(screen.queryByText("本機複核 · Private Runtime")).not.toBeInTheDocument();
  expect(
    screen.getByRole("region", { name: "WoundScope 傷口分割複核工作台" }),
  ).not.toHaveAttribute("aria-live");
  expect(screen.getByText("影像僅保留於目前本機工作階段。")).toHaveAttribute(
    "aria-live",
    "polite",
  );
  const guide = screen.getByRole("region", { name: "操作流程" });
  expect(guide).toBeVisible();
  expect(within(guide).getByText("選擇影像")).toBeVisible();
  expect(within(guide).getByText("明確開始分割")).toBeVisible();
  expect(within(guide).getByText("比較並人工複核")).toBeVisible();
  expect(within(guide).queryByRole("link")).not.toBeInTheDocument();
  expect(container.querySelector(".empty-review-state > svg")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
});

it("rejects unsupported files next to the input", async () => {
  const user = userEvent.setup({ applyAccept: false });
  render(<ReviewWorkspace status={readyStatus} />);

  await user.upload(
    screen.getByLabelText("選擇傷口影像"),
    new File(["not an image"], "notes.txt", { type: "text/plain" }),
  );

  expect(screen.getByText("僅接受 PNG、JPEG 或 WebP 影像。")).toBeVisible();
  expect(screen.getByRole("button", { name: "開始分割複核" })).toBeDisabled();
  expect(predictSpy).not.toHaveBeenCalled();
});

it("disables submission while inference is running", async () => {
  const pending = deferred<PredictionResponse>();
  predictSpy.mockReturnValue(pending.promise);
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);

  await user.upload(screen.getByLabelText("選擇傷口影像"), syntheticPngFile());
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));

  expect(screen.getByRole("button", { name: "正在執行分割…" })).toBeDisabled();
  pending.resolve(result);
  expect(await screen.findByText("需要人工複核")).toBeVisible();
});

it("revokes the prior object URL on replacement and unmount", async () => {
  const user = userEvent.setup();
  const { unmount } = render(<ReviewWorkspace status={readyStatus} />);
  const input = screen.getByLabelText("選擇傷口影像");

  await user.upload(input, syntheticPngFile("first.png"));
  await user.upload(input, syntheticPngFile("second.png"));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:woundscope-preview");

  unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
});

it("recovers from a sanitized server error", async () => {
  predictSpy.mockRejectedValueOnce(new Error("C:\\private\\model.onnx"));
  predictSpy.mockResolvedValueOnce(result);
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);

  await user.upload(screen.getByLabelText("選擇傷口影像"), syntheticPngFile());
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));
  expect(await screen.findByText("分割暫時無法完成，請重新嘗試。")).toBeVisible();
  expect(screen.queryByText(/private/)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "重新嘗試" }));
  expect(await screen.findByText("需要人工複核")).toBeVisible();
});

it("switches layers and exposes keyboard-operable comparison controls", async () => {
  predictSpy.mockResolvedValue(result);
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);
  await user.upload(screen.getByLabelText("選擇傷口影像"), syntheticPngFile());
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));
  await screen.findByText("需要人工複核");

  await user.click(screen.getByRole("button", { name: "Mask" }));
  expect(screen.getByTestId("mask-layer")).toBeVisible();
  expect(screen.getByRole("button", { name: "Mask" })).toHaveAttribute("aria-pressed", "true");

  await user.click(screen.getByRole("button", { name: "比較" }));
  const comparison = screen.getByRole("slider", { name: "Overlay 比較位置" });
  expect(comparison).toHaveAttribute("type", "range");
  expect(comparison).toHaveAttribute("min", "0");
  expect(comparison).toHaveAttribute("max", "100");
  fireEvent.change(comparison, { target: { value: "51" } });
  expect(comparison).toHaveValue("51");
  expect(screen.getByRole("slider", { name: "Overlay 透明度" })).toHaveValue("45");
});

it("enters and exits fullscreen while keeping controls available", async () => {
  predictSpy.mockResolvedValue(result);
  const requestFullscreen = vi.fn().mockResolvedValue(undefined);
  const exitFullscreen = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
    configurable: true,
    value: requestFullscreen,
  });
  Object.defineProperty(document, "exitFullscreen", {
    configurable: true,
    value: exitFullscreen,
  });
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);
  await user.upload(screen.getByLabelText("選擇傷口影像"), syntheticPngFile());
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));
  await screen.findByText("需要人工複核");

  await user.click(screen.getByRole("button", { name: "進入全螢幕" }));
  expect(requestFullscreen).toHaveBeenCalledOnce();

  Object.defineProperty(document, "fullscreenElement", {
    configurable: true,
    value: screen.getByTestId("image-stage"),
  });
  fireEvent(document, new Event("fullscreenchange"));
  await user.click(screen.getByRole("button", { name: "退出全螢幕" }));
  expect(exitFullscreen).toHaveBeenCalledOnce();

  await waitFor(() => expect(screen.getByRole("button", { name: "比較" })).toBeVisible());
});
