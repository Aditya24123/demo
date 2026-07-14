import { useMemo } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { StatePanel } from './uiAtoms';

export type SpectraDetails = {
  details?: {
    spectra?: {
      records?: Array<{
        material_id?: string;
        kind?: string;
        title?: string;
        source?: string;
        absorbing_element?: string;
        edge?: string;
        spectrum?: { x?: number[]; y?: number[]; energy?: number[]; intensity?: number[] };
      }>;
    };
  };
} | null;

const SPECTRUM_COLORS = [
  { stroke: '#6ea8ff', fill: 'rgba(110, 168, 255, 0.22)' },
  { stroke: '#7dd3a0', fill: 'rgba(125, 211, 160, 0.18)' },
  { stroke: '#c4a1ff', fill: 'rgba(196, 161, 255, 0.18)' },
  { stroke: '#f0c36a', fill: 'rgba(240, 195, 106, 0.16)' },
];

export function SpectraPanel({ details, loading, error }: { details: SpectraDetails; loading: boolean; error: string | null }) {
  if (loading) return <StatePanel title="Loading spectra" />;
  if (error) return <StatePanel title={error} danger />;
  const records = details?.details?.spectra?.records || [];
  if (!records.length) {
    return (
      <div className="flex h-full min-h-[360px] items-center justify-center p-6 text-center">
        <div className="max-w-sm">
          <SlidersHorizontal className="mx-auto mb-3 h-8 w-8" style={{ color: 'var(--cat-accent)' }} />
          <div className="text-base font-semibold">No spectra in local snapshot</div>
          <p className="mt-2 text-sm" style={{ color: 'var(--cat-text-3)' }}>
            This material has no XAS/XANES curves in the Catalyst processed index. Structure and
            property tabs still work — try another material if you need spectra demos.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-spectra-panel no-scrollbar h-full overflow-auto p-4">
      {records.slice(0, 6).map((record, index) => {
        const spectrum = record.spectrum || {};
        const x = spectrum.x || spectrum.energy || [];
        const y = spectrum.y || spectrum.intensity || [];
        const color = SPECTRUM_COLORS[index % SPECTRUM_COLORS.length];
        const title = record.title || `${record.absorbing_element || 'Element'}${record.edge ? ` · ${record.edge}` : ''} ${record.kind || 'XAS'}`;
        const subtitle = record.source || (record.kind === 'UV optical response' ? 'Cached UV optical response · energy vs intensity' : 'Absorbing edge spectrum · energy vs intensity');
        return (
          <article
            key={`${record.material_id || 'spec'}-${record.absorbing_element || 'el'}-${record.edge || index}-${index}`}
            className="jarvis-spectrum-card"
          >
            <header className="jarvis-spectrum-card-header">
              <div>
                <div className="jarvis-spectrum-title">{title}</div>
                <div className="jarvis-spectrum-subtitle">{subtitle}</div>
              </div>
              <span className="jarvis-spectrum-swatch" style={{ background: color.stroke }} />
            </header>
            <SpectrumChart x={x} y={y} stroke={color.stroke} gradientId={`spec-grad-${index}`} />
          </article>
        );
      })}
    </div>
  );
}

function SpectrumChart({
  x,
  y,
  stroke,
  gradientId,
}: {
  x: number[];
  y: number[];
  stroke: string;
  gradientId: string;
}) {
  const chart = useMemo(() => buildSpectrumChart(x, y), [x, y]);
  if (!chart) return <StatePanel title="Spectrum unavailable" />;

  const { points, minX, maxX, minY, maxY, rawCount } = chart;
  const W = 640;
  const H = 280;
  const pad = { l: 52, r: 18, t: 18, b: 40 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;

  const xTicks = niceTicks(minX, maxX, 5);
  const yTicks = niceTicks(minY, maxY, 4);

  const mapX = (v: number) => pad.l + ((v - minX) / Math.max(1e-9, maxX - minX)) * innerW;
  const mapY = (v: number) => pad.t + (1 - (v - minY) / Math.max(1e-9, maxY - minY)) * innerH;

  return (
    <div className="jarvis-spectrum-chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="jarvis-spectrum-svg" role="img" aria-label="XAS spectrum chart">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Plot background */}
        <rect
          x={pad.l}
          y={pad.t}
          width={innerW}
          height={innerH}
          rx="8"
          fill="rgba(255,255,255,0.02)"
          stroke="var(--cat-border-subtle, rgba(255,255,255,0.08))"
          strokeWidth="1"
        />

        {/* Grid + Y ticks */}
        {yTicks.map((tick) => {
          const yy = mapY(tick);
          return (
            <g key={`y-${tick}`}>
              <line
                x1={pad.l}
                x2={pad.l + innerW}
                y1={yy}
                y2={yy}
                stroke="rgba(255,255,255,0.06)"
                strokeWidth="1"
                strokeDasharray="3 4"
              />
              <text x={pad.l - 8} y={yy + 3.5} textAnchor="end" className="jarvis-spectrum-axis-label">
                {formatTick(tick)}
              </text>
            </g>
          );
        })}

        {/* X ticks */}
        {xTicks.map((tick) => {
          const xx = mapX(tick);
          return (
            <g key={`x-${tick}`}>
              <line
                x1={xx}
                x2={xx}
                y1={pad.t + innerH}
                y2={pad.t + innerH + 5}
                stroke="rgba(255,255,255,0.25)"
                strokeWidth="1"
              />
              <text x={xx} y={pad.t + innerH + 20} textAnchor="middle" className="jarvis-spectrum-axis-label">
                {formatTick(tick)}
              </text>
            </g>
          );
        })}

        {/* Area + smooth line (downsampled points in viewBox coords) */}
        <path
          d={toSvgPath(
            points.map((p) => ({ x: mapX(p.x), y: mapY(p.y) })),
            true,
            pad.t + innerH,
          )}
          fill={`url(#${gradientId})`}
          stroke="none"
        />
        <path
          d={toSvgPath(
            points.map((p) => ({ x: mapX(p.x), y: mapY(p.y) })),
            false,
          )}
          fill="none"
          stroke={stroke}
          strokeWidth="2.25"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Axis titles */}
        <text x={pad.l + innerW / 2} y={H - 6} textAnchor="middle" className="jarvis-spectrum-axis-title">
          Energy (eV)
        </text>
        <text
          x={14}
          y={pad.t + innerH / 2}
          textAnchor="middle"
          className="jarvis-spectrum-axis-title"
          transform={`rotate(-90 14 ${pad.t + innerH / 2})`}
        >
          Intensity
        </text>
      </svg>
      <div className="jarvis-spectrum-meta">
        <span>
          {points.length.toLocaleString()} pts
          {rawCount > points.length ? ` · downsampled from ${rawCount.toLocaleString()}` : ''}
        </span>
        <span>
          {formatTick(minX)}–{formatTick(maxX)} eV
        </span>
      </div>
    </div>
  );
}

type Pt = { x: number; y: number };

function buildSpectrumChart(x: number[], y: number[]) {
  if (!Array.isArray(x) || !Array.isArray(y) || !x.length || !y.length) return null;

  const raw: Pt[] = [];
  const n = Math.min(x.length, y.length);
  for (let i = 0; i < n; i += 1) {
    const xi = Number(x[i]);
    const yi = Number(y[i]);
    if (!Number.isFinite(xi) || !Number.isFinite(yi)) continue;
    raw.push({ x: xi, y: yi });
  }
  if (raw.length < 2) return null;

  raw.sort((a, b) => a.x - b.x);
  // Collapse exact-x duplicates (keep max intensity — XAS peaks matter).
  const collapsed: Pt[] = [];
  for (const p of raw) {
    const last = collapsed[collapsed.length - 1];
    if (last && Math.abs(last.x - p.x) < 1e-9) {
      if (p.y > last.y) last.y = p.y;
    } else {
      collapsed.push({ ...p });
    }
  }

  const points = downsampleLttb(collapsed, 220);
  let minX = points[0].x;
  let maxX = points[0].x;
  let minY = points[0].y;
  let maxY = points[0].y;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  // Gentle pad so peaks/valleys don't kiss the frame.
  const yPad = Math.max((maxY - minY) * 0.08, Math.abs(maxY) * 0.02, 1e-6);
  minY -= yPad;
  maxY += yPad;
  if (maxX <= minX) maxX = minX + 1;

  return {
    points,
    rawCount: collapsed.length,
    minX,
    maxX,
    minY,
    maxY,
  };
}

/** Largest-Triangle-Three-Buckets downsampling — keeps peaks without jagged noise. */
function downsampleLttb(data: Pt[], threshold: number): Pt[] {
  if (data.length <= threshold || threshold < 3) return data;
  const sampled: Pt[] = [data[0]];
  const bucketSize = (data.length - 2) / (threshold - 2);
  let a = 0;

  for (let i = 0; i < threshold - 2; i += 1) {
    const start = Math.floor((i + 1) * bucketSize) + 1;
    const end = Math.min(Math.floor((i + 2) * bucketSize) + 1, data.length);
    let avgX = 0;
    let avgY = 0;
    const count = Math.max(1, end - start);
    for (let j = start; j < end; j += 1) {
      avgX += data[j].x;
      avgY += data[j].y;
    }
    avgX /= count;
    avgY /= count;

    const rangeOff = Math.floor(i * bucketSize) + 1;
    const rangeTo = Math.min(Math.floor((i + 1) * bucketSize) + 1, data.length);
    const pointA = data[a];
    let maxArea = -1;
    let nextA = rangeOff;
    for (let j = rangeOff; j < rangeTo; j += 1) {
      const area = Math.abs(
        (pointA.x - avgX) * (data[j].y - pointA.y) - (pointA.x - data[j].x) * (avgY - pointA.y),
      );
      if (area > maxArea) {
        maxArea = area;
        nextA = j;
      }
    }
    sampled.push(data[nextA]);
    a = nextA;
  }
  sampled.push(data[data.length - 1]);
  return sampled;
}

function toSvgPath(points: Pt[], closeToBaseline: boolean, baselineY = 0): string {
  if (points.length < 2) return '';
  // Catmull-Rom → cubic Bezier for a smooth XAS-looking curve.
  const d: string[] = [`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`];
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d.push(
      `C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`,
    );
  }
  if (closeToBaseline) {
    const last = points[points.length - 1];
    const first = points[0];
    d.push(`L ${last.x.toFixed(2)} ${baselineY.toFixed(2)}`);
    d.push(`L ${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`);
  }
  return d.join(' ');
}

function niceTicks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [min];
  const span = max - min;
  const step = niceStep(span / Math.max(1, count - 1));
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) {
    if (v >= min - step * 0.01 && v <= max + step * 0.01) ticks.push(Number(v.toPrecision(12)));
    if (ticks.length > 12) break;
  }
  if (!ticks.length) return [min, max];
  return ticks;
}

function niceStep(rough: number): number {
  const exp = Math.floor(Math.log10(Math.max(rough, 1e-12)));
  const base = rough / 10 ** exp;
  let nice = 1;
  if (base <= 1.5) nice = 1;
  else if (base <= 3) nice = 2;
  else if (base <= 7) nice = 5;
  else nice = 10;
  return nice * 10 ** exp;
}

function formatTick(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1000) return v.toFixed(0);
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 10) return v.toFixed(2);
  if (abs >= 1) return v.toFixed(3);
  return v.toPrecision(3);
}
