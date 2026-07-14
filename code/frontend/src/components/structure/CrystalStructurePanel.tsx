import { Box, Loader2 } from 'lucide-react';
import { useMemo, type ReactNode } from 'react';
import type { Structure3DVM } from '@/catalyst/bridge/viewModels';
import { CrystalStructureViewer } from './CrystalStructureViewer';
import { ElementLegend } from './ElementLegend';
import { StructureMetrics } from './StructureMetrics';
import { useCatalystLayout } from '@/catalyst/bridge/hooks';

type CrystalStructurePanelProps = {
  structure: Structure3DVM | null;
  isLoading?: boolean;
  error?: string | null;
};

export function CrystalStructurePanel({ structure, isLoading = false, error = null }: CrystalStructurePanelProps) {
  const { demoMaterialAnimation } = useCatalystLayout();
  const showBonds = true;
  const showUnitCell = false;
  const atomScale = 0.42;
  const hasStructureSites = Boolean(structure?.sites?.length);

  const elements = useMemo(() => {
    const unique = new Set<string>();
    for (const site of structure?.sites || []) {
      const symbol = String(site.element || site.label || '').trim();
      if (symbol) unique.add(symbol);
      if (unique.size >= 18) break;
    }
    return Array.from(unique);
  }, [structure]);

  return (
    <div className="jarvis-structure-panel jarvis-structure-panel-fill">
      <div className="jarvis-structure-viewport jarvis-structure-viewport-fill">
        {isLoading ? (
          <StructureState icon={<Loader2 className="h-5 w-5 animate-spin" />} title="Loading structure" text="Resolving crystal sites and lattice." />
        ) : error ? (
          <StructureState danger icon={<Box className="h-5 w-5" />} title="Structure unavailable" text={error} />
        ) : !hasStructureSites ? (
          <StructureState
            icon={<Box className="h-5 w-5" />}
            title="Structure unavailable"
            text={structure?.message || 'Full 3D structure is not present for this material.'}
          />
        ) : (
          <>
            <CrystalStructureViewer
              structure={structure}
              showBonds={showBonds}
              showUnitCell={showUnitCell}
              atomScale={atomScale}
              resetNonce={0}
              demoAnimation={demoMaterialAnimation}
            />
            {/* Info card top-left; legend top-right. Refresh control removed. */}
            <div className="jarvis-structure-float jarvis-structure-float-top-left">
              <StructureMetrics structure={structure} floating />
            </div>
            <div className="jarvis-structure-float jarvis-structure-float-top-right">
              <ElementLegend elements={elements} floating />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StructureState({
  icon,
  title,
  text,
  danger = false,
}: {
  icon: ReactNode;
  title: string;
  text: string;
  danger?: boolean;
}) {
  return (
    <div className="flex h-full min-h-[380px] items-center justify-center text-center">
      <div className="max-w-sm">
        <div
          className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-full"
          style={{ background: danger ? 'rgba(220,38,38,0.12)' : 'var(--accent-muted)', color: danger ? 'var(--danger)' : 'var(--accent)' }}
        >
          {icon}
        </div>
        <div className="text-lg font-semibold" style={{ color: 'var(--text-1)' }}>
          {title}
        </div>
        <p className="mt-2 text-sm" style={{ color: 'var(--text-3)' }}>
          {text}
        </p>
      </div>
    </div>
  );
}
