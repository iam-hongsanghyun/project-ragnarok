/**
 * Plugins tab — install, configure and run frontend plugins.
 *
 * Plugins are installed into a frontend "plugin location" (browser storage) and
 * run in the browser. A plugin may replace the whole model (transform),
 * contribute sheets + constraint lines (contribute), and read the run output
 * (analyze). It never talks to the Ragnarok backend — the frontend does.
 */
import React, { useRef, useState } from 'react';
import { WorkbookModel } from '../../shared/types';
import { FrontendPluginHost, InstalledPlugin } from './frontendPlugins';
import { loadPluginModule, pluginCapabilities } from './pluginRuntime';
import { useToast } from '../../shared/components/Toast';

export interface PluginManagerPanelProps {
  host: FrontendPluginHost;
  model: WorkbookModel;
  /** Replace the whole workbook (e.g. an importer's transform). */
  onReplaceModel: (next: WorkbookModel) => void;
  /** Merge contributed sheets into the current model. */
  onMergeSheets: (sheets: Record<string, WorkbookModel[string]>) => void;
  customDsl: string;
  onCustomDslChange: (text: string) => void;
  results: unknown;
}

export function PluginManagerPanel({ host, model, onReplaceModel, onMergeSheets, customDsl, onCustomDslChange, results }: PluginManagerPanelProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const { showToast } = useToast();
  const [analysis, setAnalysis] = useState<Record<string, Record<string, unknown>>>({});

  const onPick = async (file: File | undefined) => {
    if (!file) return;
    const result = await host.install(file);
    showToast(result.ok ? `Installed "${result.id}"` : `Install failed: ${result.error}`, result.ok ? 'success' : 'error');
    if (fileRef.current) fileRef.current.value = '';
  };

  const apply = (plugin: InstalledPlugin) => {
    const config = host.getConfig(plugin.id);
    try {
      const mod = loadPluginModule(plugin);
      if (mod.transform) {
        const next = mod.transform(model, config);
        if (!next || typeof next !== 'object') throw new Error('transform() did not return a model.');
        onReplaceModel(next as WorkbookModel);
        showToast(`${plugin.name}: model replaced.`, 'success');
        return;
      }
      if (mod.contribute) {
        const out = mod.contribute(model, config) || {};
        if (out.sheets && typeof out.sheets === 'object') {
          onMergeSheets(out.sheets);
        }
        if (Array.isArray(out.constraints) && out.constraints.length) {
          const block = [`# ${plugin.name} (plugin)`, ...out.constraints].join('\n');
          onCustomDslChange(customDsl.trim() ? `${customDsl.replace(/\s+$/, '')}\n${block}\n` : `${block}\n`);
        }
        showToast(`${plugin.name}: contributed to the model.`, 'success');
        return;
      }
      showToast(`${plugin.name} has no transform/contribute hook.`, 'error');
    } catch (err) {
      showToast(`${plugin.name}: ${err instanceof Error ? err.message : 'failed'}`, 'error');
    }
  };

  const analyze = (plugin: InstalledPlugin) => {
    const config = host.getConfig(plugin.id);
    try {
      const mod = loadPluginModule(plugin);
      if (!mod.analyze) { showToast(`${plugin.name} has no analyze hook.`, 'error'); return; }
      const out = mod.analyze(results, config) || {};
      setAnalysis((prev) => ({ ...prev, [plugin.id]: out }));
    } catch (err) {
      showToast(`${plugin.name}: ${err instanceof Error ? err.message : 'analyze failed'}`, 'error');
    }
  };

  return (
    <section className="constraints-workspace-section">
      <header className="constraints-workspace-section-header">
        <h3>Plugins</h3>
        <p>Install a plugin package (<code>.zip</code> with a <code>module.json</code> + JS entry). Plugins run in the browser — they feed the model and read run output, and never contact the Ragnarok backend directly.</p>
      </header>

      <div className="sg-setting-row">
        <input ref={fileRef} type="file" accept=".zip" style={{ display: 'none' }} onChange={(e) => onPick(e.target.files?.[0])} />
        <div className="sg-btn-row">
          <button className="tb-btn" onClick={() => fileRef.current?.click()}>Install plugin…</button>
        </div>
      </div>

      {host.installed.length === 0 ? (
        <div className="constraints-empty">
          <p>No plugins installed. Use “Install plugin…” to add one.</p>
        </div>
      ) : (
        <div className="plugin-list">
          {host.installed.map((p) => {
            const enabled = host.isEnabled(p.id);
            const caps = pluginCapabilities(p);
            const cfg = host.getConfig(p.id);
            const out = analysis[p.id];
            return (
              <div key={p.id} className="plugin-list-item">
                <label className="plugin-list-head">
                  <input type="checkbox" className="gcc-check" checked={enabled} onChange={(e) => host.toggle(p.id, e.target.checked)} />
                  <strong>{p.name}</strong>
                  {p.version && <span className="plugin-list-version">v{p.version}</span>}
                  <button className="gcc-del" title="Uninstall" onClick={() => host.uninstall(p.id)}>x</button>
                </label>
                {p.description && <p className="sg-setting-hint">{p.description}</p>}
                {enabled && (
                  <div className="plugin-fe-config">
                    <label className="sg-setting-label">Config (JSON)</label>
                    <textarea
                      className="constraints-dsl-input"
                      rows={3}
                      value={JSON.stringify(cfg, null, 2)}
                      onChange={(e) => {
                        try { host.setConfig(p.id, JSON.parse(e.target.value || '{}')); } catch { /* keep typing */ }
                      }}
                    />
                    <div className="sg-btn-row">
                      {(caps.transform || caps.contribute) && (
                        <button className="tb-btn" onClick={() => apply(p)}>Apply to model</button>
                      )}
                      {caps.analyze && (
                        <button className="tb-btn tb-btn--muted" onClick={() => analyze(p)}>Analyze output</button>
                      )}
                    </div>
                    {out && (
                      <pre className="plugin-analyze-out">{JSON.stringify(out, null, 2)}</pre>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
