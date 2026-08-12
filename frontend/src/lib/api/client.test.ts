import { ApiError, fetchModelStatus } from "./client";

const safeStatus = {
  mode: "showcase",
  model_available: false,
  calibration_available: false,
  model_label: "EfficientNet-B0 U-Net / ONNX",
  model_sha256_prefix: null,
  provider: "unavailable",
  message: "研究展示模式",
};

it("returns typed model status", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(safeStatus), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(fetchModelStatus()).resolves.toEqual(safeStatus);
});

it("maps structured API errors without exposing arbitrary response text", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "MODEL_NOT_AVAILABLE", message: "尚未就緒" } }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  await expect(fetchModelStatus()).rejects.toEqual(
    new ApiError("MODEL_NOT_AVAILABLE", "尚未就緒", 503),
  );
});

it("uses a fixed message for network failures", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private network detail")));

  await expect(fetchModelStatus()).rejects.toEqual(
    new ApiError("NETWORK_ERROR", "無法連線至本機 WoundScope 服務。", 0),
  );
});
