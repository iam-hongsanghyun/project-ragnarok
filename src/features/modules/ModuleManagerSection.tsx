import React from 'react';
import { ModuleDescriptor, ModuleHostInventory } from '../../shared/types';

interface ModuleManagerSectionProps {
  inventory: ModuleHostInventory | null;
  loading: boolean;
  error: string | null;
  enabledIds: string[];
  isEnabled: (moduleId: string) => boolean;
  isEnableEligible: (module: ModuleDescriptor) => boolean;
  onRefresh: () => void;
  onToggleEnabled: (moduleId: string, enabled: boolean) => void;
}

function statusLabel(module: ModuleDescriptor): string {
  if (module.status === 'ready' && module.entryExists) return 'Ready';
  if (module.status === 'incompatible') return 'Incompatible';
  return 'Invalid';
}

export function ModuleManagerSection({
  inventory,
  loading,
  error,
  enabledIds,
  isEnabled,
  isEnableEligible,
  onRefresh,
  onToggleEnabled,
}: ModuleManagerSectionProps) {
  const modules = inventory?.modules ?? [];
  const roots = inventory?.roots ?? [];

  return (
    <div className="sg-setting-row">
      <div className="sg-module-head">
        <div>
          <p className="sg-setting-section-title">Local module host</p>
          <p className="sg-setting-hint">
            {inventory
              ? `SDK ${inventory.host.sdkVersion} · ${inventory.host.runtimeMode} · ${enabledIds.length} enabled`
              : 'Discovers trusted local modules and exposes host readiness.'}
          </p>
        </div>
        <button className="tb-btn tb-btn--muted" onClick={onRefresh} disabled={loading}>
          {loading ? 'Scanning…' : 'Refresh'}
        </button>
      </div>

      {error && <p className="sg-error-text">{error}</p>}

      {roots.length > 0 && (
        <div className="sg-module-roots">
          {roots.map((root) => (
            <div key={`${root.label}-${root.path}`} className="sg-module-root">
              <span className="sg-module-root-label">{root.label}</span>
              <code className="sg-module-root-path">{root.path}</code>
              <span className={`sg-module-root-status${root.exists && root.isDirectory ? ' is-ok' : ''}`}>
                {root.exists && root.isDirectory ? 'available' : 'missing'}
              </span>
            </div>
          ))}
        </div>
      )}

      {modules.length === 0 ? (
        <p className="sg-setting-hint">
          No local modules discovered yet. Drop module folders containing `module.json` into one of the configured module roots.
        </p>
      ) : (
        <div className="sg-module-list">
          {modules.map((module) => {
            const eligible = isEnableEligible(module);
            const enabled = isEnabled(module.id) && eligible;
            return (
              <div key={`${module.id}-${module.modulePath}`} className="sg-module-card">
                <div className="sg-module-card-top">
                  <div>
                    <div className="sg-module-name-row">
                      <strong>{module.name || module.id}</strong>
                      <span className={`sg-module-status sg-module-status--${module.status}`}>{statusLabel(module)}</span>
                    </div>
                    <p className="sg-module-meta">
                      {module.id || 'unidentified'} · v{module.version || '—'} · sdk {module.sdkVersion || '—'}
                    </p>
                  </div>
                  <button
                    className={`tb-btn sg-solver-btn${enabled ? '' : ' tb-btn--muted'}`}
                    disabled={!eligible}
                    onClick={() => onToggleEnabled(module.id, !enabled)}
                    title={eligible ? 'Enable this module for future host execution hooks.' : 'Only ready modules can be enabled.'}
                  >
                    {enabled ? 'Enabled' : 'Enable'}
                  </button>
                </div>
                {module.description && <p className="sg-setting-hint">{module.description}</p>}
                <p className="sg-module-meta">
                  Capabilities: {module.capabilities.length > 0 ? module.capabilities.join(', ') : '—'}
                </p>
                <p className="sg-module-meta">
                  Permissions: {module.permissions.length > 0 ? module.permissions.join(', ') : '—'}
                </p>
                <p className="sg-module-meta">
                  Root: {module.rootLabel}
                </p>
                <code className="sg-module-root-path">{module.modulePath}</code>
                {module.diagnostics.length > 0 && (
                  <div className="sg-module-diag-list">
                    {module.diagnostics.map((item, index) => (
                      <p key={`${module.id}-diag-${index}`} className="sg-error-text">{item}</p>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
