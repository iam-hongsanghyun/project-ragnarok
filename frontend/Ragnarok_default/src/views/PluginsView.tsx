/**
 * Plugins view — install, configure and run frontend-only plugins.
 *
 * Parallel to Model / Settings / Analytics. Plugins are a frontend concern: the
 * Ragnarok backend never hosts or runs them.
 */
import React from 'react';
import { WorkbookModel } from '../shared/types';
import { PluginManagerPanel } from '../features/plugins/PluginManagerPanel';
import { FrontendPluginHost } from '../features/plugins/frontendPlugins';

interface Props {
  host: FrontendPluginHost;
  model: WorkbookModel;
  onReplaceModel: (next: WorkbookModel) => void;
  onMergeSheets: (sheets: Record<string, WorkbookModel[string]>) => void;
  customDsl: string;
  onCustomDslChange: (text: string) => void;
  results: unknown;
}

export function PluginsView(props: Props) {
  return (
    <div className="view plugins-view">
      <main className="view-main">
        <PluginManagerPanel
          host={props.host}
          model={props.model}
          onReplaceModel={props.onReplaceModel}
          onMergeSheets={props.onMergeSheets}
          customDsl={props.customDsl}
          onCustomDslChange={props.onCustomDslChange}
          results={props.results}
        />
      </main>
    </div>
  );
}
