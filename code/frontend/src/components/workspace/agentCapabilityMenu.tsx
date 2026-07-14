import { useState } from 'react';
import { Check, ChevronRight, FileUp, ImagePlus, MonitorUp } from 'lucide-react';
import { modelDisplayLabel } from '@/catalyst/bridge/modelLabels';

export function CapabilityMenu({
  modelId,
  models,
  supportsImages,
  voiceActive,
  screenActive,
  onSelectModel,
  onAddFile,
  onToggleScreenShare,
  onClose,
}: {
  modelId: string;
  models: string[];
  supportsImages: boolean;
  voiceActive?: boolean;
  screenActive?: boolean;
  onSelectModel: (modelId: string) => void;
  onAddFile: () => void;
  onToggleScreenShare?: () => void;
  onClose: () => void;
}) {
  const [panel, setPanel] = useState<'root' | 'model'>('root');
  const shortModel = modelDisplayLabel(modelId);

  return (
    <div className="jarvis-agent-capability-menu" role="menu" aria-label="Composer options">
      {panel === 'root' ? (
        <>
          <button type="button" className="jarvis-cap-row" role="menuitem" onClick={() => setPanel('model')}>
            <span>Model</span>
            <span className="jarvis-cap-row-meta">
              <span className="truncate">{shortModel}</span>
              <ChevronRight className="h-4 w-4 shrink-0 opacity-70" />
            </span>
          </button>
          <div className="jarvis-capability-divider" />
          <button
            type="button"
            className="jarvis-cap-row"
            role="menuitem"
            onClick={() => {
              onAddFile();
              onClose();
            }}
          >
            <span className="jarvis-cap-row-start">
              {supportsImages ? <ImagePlus className="h-4 w-4 opacity-80" /> : <FileUp className="h-4 w-4 opacity-80" />}
              Add files
            </span>
          </button>
          {onToggleScreenShare ? (
            <button
              type="button"
              className="jarvis-cap-row"
              role="menuitem"
              onClick={() => {
                onToggleScreenShare();
                onClose();
              }}
            >
              <span className="jarvis-cap-row-start">
                <MonitorUp className="h-4 w-4 opacity-80" />
                {screenActive ? 'Stop screen share' : voiceActive ? 'Share screen' : 'Voice + share screen'}
              </span>
              {screenActive ? <Check className="h-4 w-4 shrink-0 opacity-80" strokeWidth={2.4} /> : null}
            </button>
          ) : null}
        </>
      ) : null}

      {panel === 'model' ? (
        <>
          <button type="button" className="jarvis-cap-panel-title" onClick={() => setPanel('root')}>
            Model
          </button>
          <div className="jarvis-cap-scroll">
            {models.map((model) => {
              const selected = model === modelId || model.endsWith(modelId) || modelId.endsWith(model);
              const label = modelDisplayLabel(model);
              return (
                <button
                  key={model}
                  type="button"
                  className={selected ? 'jarvis-cap-option active' : 'jarvis-cap-option'}
                  role="menuitemradio"
                  aria-checked={selected}
                  onClick={() => {
                    onSelectModel(model);
                    setPanel('root');
                  }}
                >
                  <span className="truncate">{label}</span>
                  {selected ? <Check className="h-4 w-4 shrink-0" strokeWidth={2.4} /> : null}
                </button>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}
