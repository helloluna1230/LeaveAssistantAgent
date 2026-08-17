export interface ChartSpec {
  type: "pie" | "bar" | "line";
  title?: string;
  unit?: string;
  data: { label: string; value: number }[];
}

const PALETTE = [
  "#6c7cff",
  "#37c8a8",
  "#f0a63a",
  "#e8637a",
  "#9b7bff",
  "#4fb0ff",
  "#e05fae",
  "#8bcf5a",
];

/** Parse ```chart … ``` fenced blocks out of assistant text. */
export function extractCharts(text: string): { clean: string; charts: ChartSpec[] } {
  const charts: ChartSpec[] = [];
  const fence = /```chart\s*([\s\S]*?)```/g;
  let clean = text.replace(fence, (_m, body) => {
    try {
      const spec = JSON.parse(String(body).trim()) as ChartSpec;
      if (spec && Array.isArray(spec.data) && spec.data.length) charts.push(spec);
    } catch {
      // Leave malformed blocks out of the transcript silently.
    }
    return "";
  });
  // Drop broken sandbox image links the model may still emit.
  clean = clean.replace(/!\[[^\]]*\]\(sandbox:[^)]*\)/g, "").trim();
  return { clean, charts };
}

function polar(cx: number, cy: number, r: number, a: number) {
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function Pie({ spec }: { spec: ChartSpec }) {
  const total = spec.data.reduce((s, d) => s + Math.max(0, d.value), 0) || 1;
  const cx = 90;
  const cy = 90;
  const r = 80;
  let a0 = -Math.PI / 2;
  return (
    <div className="chart-body">
      <svg viewBox="0 0 180 180" width="180" height="180" role="img">
        {spec.data.map((d, i) => {
          const frac = Math.max(0, d.value) / total;
          const a1 = a0 + frac * 2 * Math.PI;
          const [x0, y0] = polar(cx, cy, r, a0);
          const [x1, y1] = polar(cx, cy, r, a1);
          const large = a1 - a0 > Math.PI ? 1 : 0;
          const path =
            frac >= 0.999
              ? `M ${cx - r} ${cy} a ${r} ${r} 0 1 0 ${2 * r} 0 a ${r} ${r} 0 1 0 ${-2 * r} 0`
              : `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z`;
          a0 = a1;
          return <path key={i} d={path} fill={PALETTE[i % PALETTE.length]} />;
        })}
      </svg>
      <ul className="chart-legend">
        {spec.data.map((d, i) => {
          const pct = ((Math.max(0, d.value) / total) * 100).toFixed(1);
          return (
            <li key={i}>
              <span className="swatch" style={{ background: PALETTE[i % PALETTE.length] }} />
              {d.label}: {d.value}
              {spec.unit ?? ""} ({pct}%)
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Bars({ spec }: { spec: ChartSpec }) {
  const max = Math.max(1, ...spec.data.map((d) => d.value));
  return (
    <div className="chart-bars">
      {spec.data.map((d, i) => (
        <div className="bar-row" key={i}>
          <span className="bar-label">{d.label}</span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${(d.value / max) * 100}%`, background: PALETTE[i % PALETTE.length] }}
            />
          </div>
          <span className="bar-value">
            {d.value}
            {spec.unit ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

function Line({ spec }: { spec: ChartSpec }) {
  const w = 320;
  const h = 160;
  const pad = 28;
  const max = Math.max(1, ...spec.data.map((d) => d.value));
  const n = spec.data.length;
  const x = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(1, n - 1);
  const y = (v: number) => h - pad - (v / max) * (h - 2 * pad);
  const pts = spec.data.map((d, i) => `${x(i)},${y(d.value)}`).join(" ");
  return (
    <div className="chart-body">
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img">
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#3a3f5c" />
        <polyline points={pts} fill="none" stroke="#6c7cff" strokeWidth="2" />
        {spec.data.map((d, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(d.value)} r="3" fill="#37c8a8" />
            <text x={x(i)} y={h - pad + 14} fontSize="9" fill="#9aa0c0" textAnchor="middle">
              {d.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export function Chart({ spec }: { spec: ChartSpec }) {
  return (
    <div className="chart-card">
      {spec.title && <div className="chart-title">{spec.title}</div>}
      {spec.type === "pie" && <Pie spec={spec} />}
      {spec.type === "bar" && <Bars spec={spec} />}
      {spec.type === "line" && <Line spec={spec} />}
    </div>
  );
}
