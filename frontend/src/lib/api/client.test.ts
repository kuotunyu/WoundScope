import { ApiError, fetchModelStatus, predictImage } from "./client";

const safePrediction = {
  overlay_data_url: "data:image/png;base64,b3ZlcmxheQ==",
  mask_data_url: "data:image/png;base64,bWFzaw==",
  wound_pixel_ratio: 0.2,
  confidence_score: 0.8,
  confidence_label: "模型分割信心，非臨床信心",
  inference_ms: 14,
  low_confidence: false,
  review_reasons: [],
  provider: "CPUExecutionProvider",
};

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

it("posts an image under a neutral filename", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(safePrediction), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const privateName = new File(["pixels"], "patient-name.jpeg", { type: "image/jpeg" });

  await expect(predictImage(privateName)).resolves.toEqual(safePrediction);

  const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(path).toBe("/api/predict");
  expect(request.method).toBe("POST");
  const upload = (request.body as FormData).get("image") as File;
  expect(upload.name).toBe("upload.jpg");
  expect(upload.name).not.toContain("patient-name");
});

it("maps prediction errors through the same sanitized API contract", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "INFERENCE_FAILED", message: "分割推論失敗。" } }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  await expect(
    predictImage(new File(["pixels"], "input.png", { type: "image/png" })),
  ).rejects.toEqual(new ApiError("INFERENCE_FAILED", "分割推論失敗。", 500));
});
