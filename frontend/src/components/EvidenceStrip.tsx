const evidence = [
  { value: "0.8508", label: "U-Net observed Dice", scope: "3 seeds · 鎖定 split" },
  { value: "200", label: "Official Validation", scope: "完整影像證據／seed" },
  { value: "2,000×", label: "Image-level Bootstrap", scope: "95% CI 推估" },
  { value: "2", label: "模型架構", scope: "U-Net · SegFormer-B0" },
];

export function EvidenceStrip() {
  return (
    <section className="evidence-strip" aria-labelledby="evidence-title">
      <div className="evidence-heading">
        <h2 className="eyebrow" id="evidence-title">
          已驗證證據
        </h2>
        <p>Official Validation · 200 張；非 official-test、非臨床效能</p>
      </div>
      <div className="evidence-grid">
        {evidence.map((item) => (
          <article className="evidence-item" key={item.label}>
            <strong>{item.value}</strong>
            <span>{item.label}</span>
            <small>{item.scope}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
