import { elementColor } from './elementColors';

type ElementLegendProps = {
  elements: string[];
  floating?: boolean;
};

export function ElementLegend({ elements, floating = false }: ElementLegendProps) {
  if (!elements.length) return null;
  return (
    <div className={floating ? 'jarvis-element-legend-float' : 'flex flex-wrap gap-1.5'}>
      {elements.map((el) => (
        <span
          key={el}
          className={
            floating
              ? 'jarvis-element-legend-chip'
              : 'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px]'
          }
          style={
            floating
              ? undefined
              : { borderColor: 'var(--border)', background: 'var(--surface-2)', color: 'var(--text-2)' }
          }
        >
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: elementColor(el) }} />
          <span className="font-mono">{el}</span>
        </span>
      ))}
    </div>
  );
}
