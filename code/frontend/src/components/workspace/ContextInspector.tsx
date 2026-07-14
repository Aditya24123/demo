import { useEffect, useState } from 'react';
import type { InspectorTab } from '@/catalyst/ui-state/layoutStore';
import type { WorkspaceVM } from '@/catalyst/bridge/viewModels';
import { AgentChatBody } from './AgentChatBody';
import { ABOUT_TABS } from './constants';
import { JarvisRawIcon, XIcon } from './JarvisIcons';
import { EmptyGroupState, PropertyGroupTab } from './PropertyPanels';
import { findPropertyGroup } from './utils';

export function ContextInspector({
  workspace,
  propertyDetails,
  propertyLoading,
  propertyError,
  spectraDetails,
  inspectorTab,
  setInspectorTab,
  onCollapse,
}: {
  workspace: WorkspaceVM | null;
  propertyDetails: any;
  propertyLoading: boolean;
  propertyError: string | null;
  evidenceDetails: any;
  spectraDetails: any;
  inspectorTab: InspectorTab;
  setInspectorTab: (tab: InspectorTab) => void;
  onCollapse: () => void;
}) {
  const [activeAboutTab, setActiveAboutTab] = useState<(typeof ABOUT_TABS)[number]['id']>('thermodynamic');
  const activePanel = inspectorTab === 'agent' ? 'agent' : 'properties';
  const spectraCount = Number(spectraDetails?.details?.spectra?.count || propertyDetails?.details?.spectra?.count || 0);

  return (
    <aside className="jarvis-right-panel">
      <div className="jarvis-right-topbar">
        <div className="jarvis-right-tabs">
          <button
            type="button"
            className={activePanel === 'agent' ? 'jarvis-right-tab active' : 'jarvis-right-tab'}
            onClick={() => setInspectorTab('agent')}
          >
            <JarvisRawIcon name="chat" className="h-4 w-4" />
            <span>Agent</span>
          </button>
          <button
            type="button"
            className={activePanel === 'properties' ? 'jarvis-right-tab active' : 'jarvis-right-tab'}
            onClick={() => setInspectorTab('properties')}
          >
            <img src="/icons/info.png" alt="" className="jarvis-tab-icon-img" draggable={false} />
            <span>Properties</span>
          </button>
        </div>
        <button type="button" onClick={onCollapse} className="jarvis-right-close" title="Close panel" aria-label="Close panel">
          <XIcon className="h-5 w-5" />
        </button>
      </div>

      {activePanel === 'agent' ? (
        <AgentChatBody />
      ) : !workspace ? (
        <div className="jarvis-properties-body">
          <EmptyGroupState label="No material open" compactText="Open a material to inspect properties." />
        </div>
      ) : (
        <PropertiesPanel
          workspace={workspace}
          propertyDetails={propertyDetails}
          propertyLoading={propertyLoading}
          propertyError={propertyError}
          spectraCount={spectraCount}
          activeAboutTab={activeAboutTab}
          setActiveAboutTab={setActiveAboutTab}
        />
      )}
    </aside>
  );
}

function PropertiesPanel({
  workspace,
  propertyDetails,
  propertyLoading,
  propertyError,
  spectraCount,
  activeAboutTab,
  setActiveAboutTab,
}: {
  workspace: WorkspaceVM;
  propertyDetails: any;
  propertyLoading: boolean;
  propertyError: string | null;
  spectraCount: number;
  activeAboutTab: (typeof ABOUT_TABS)[number]['id'];
  setActiveAboutTab: (id: (typeof ABOUT_TABS)[number]['id']) => void;
}) {
  const activeGroup = activeAboutTab === 'evidence' ? null : findPropertyGroup(propertyDetails, activeAboutTab);
  const caps = workspace.capabilities || null;
  const description = workspace.description || null;

  const propertyTabs = ABOUT_TABS.filter((tab) => {
    if (tab.id === 'evidence') return false;
    if (!caps) return true;
    if (tab.id === 'thermodynamic') return caps.thermo !== false;
    if (tab.id === 'electronic') return caps.electronic !== false;
    if (tab.id === 'magnetic') return caps.magnetic !== false;
    if (tab.id === 'mechanical') return caps.mechanical !== false;
    if (tab.id === 'dielectric') return caps.dielectric !== false;
    if (tab.id === 'surface') return caps.surface === true;
    if (tab.id === 'bonds') return caps.bonds === true;
    if (tab.id === 'spectra') return Boolean(caps.spectra) || spectraCount > 0;
    return true;
  });

  const filteredTabs = propertyDetails
    ? propertyTabs.filter((tab) => {
        if (tab.id === 'spectra') return spectraCount > 0 || Boolean(caps?.spectra);
        const group = findPropertyGroup(propertyDetails, tab.id);
        if (!group) return false;
        const available = (group.items || []).filter(
          (item: any) => item.available !== false && item.value !== null && item.value !== undefined && item.value !== '',
        );
        return available.length > 0;
      })
    : propertyTabs;

  useEffect(() => {
    if (!filteredTabs.length) return;
    if (!filteredTabs.some((tab) => tab.id === activeAboutTab)) {
      setActiveAboutTab(filteredTabs[0].id);
    }
  }, [activeAboutTab, filteredTabs, setActiveAboutTab]);

  return (
    <div className="jarvis-properties-body">
      {/* Title + property tabs stay pinned; long copy scrolls below. */}
      <div className="jarvis-properties-sticky">
        <div className="jarvis-properties-title-row">
          <div className="min-w-0">
            <h2 className="jarvis-properties-title truncate">{workspace.title}</h2>
            <div className="jarvis-code jarvis-muted mt-1 truncate text-[12px]">
              {workspace.resolvedMaterialId}
              {workspace.mpMaterialId && workspace.mpMaterialId !== workspace.resolvedMaterialId
                ? ` ? ${workspace.mpMaterialId}`
                : ''}
            </div>
          </div>
        </div>

        <div className="jarvis-property-tabs no-scrollbar">
          {filteredTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveAboutTab(tab.id)}
              className={activeAboutTab === tab.id ? 'jarvis-property-tab active' : 'jarvis-property-tab'}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="jarvis-properties-scroll">
        {description ? (
          <div className="jarvis-property-card jarvis-material-summary">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cat-text-3)' }}>
              Description
            </div>
            <p className="jarvis-material-summary-text text-[13px] leading-5" style={{ color: 'var(--cat-text-2)' }}>
              {description}
            </p>
          </div>
        ) : null}

        <div className="jarvis-property-card">
          {propertyLoading || propertyError || !propertyDetails ? (
            <EmptyGroupState
              label={propertyLoading ? 'Loading properties' : 'Properties unavailable'}
              compactText={propertyLoading ? 'Loading available properties?' : propertyError || 'No property groups returned.'}
            />
          ) : activeAboutTab === 'spectra' && spectraCount === 0 ? (
            <EmptyGroupState label="Spectra" />
          ) : (
            <PropertyGroupTab group={activeGroup} label={ABOUT_TABS.find((tab) => tab.id === activeAboutTab)?.label || activeAboutTab} />
          )}
        </div>
      </div>
    </div>
  );
}
