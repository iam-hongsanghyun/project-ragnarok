/**
 * RunDialog — minimal modal for kicking off a solve. Uses the same visual
 * language as the Validation pane: eyebrow + h2 header, bordered sections
 * with uppercase section titles, tb-btn pills for choices.
 *
 * Two sections only — Planning (Single period / Pathway) and Optimisation
 * settings (Rolling horizon, Force LP, Dry run as single toggle buttons).
 * Everything else lives in the sidebar.
 */
import React from 'react';
import { PathwayConfig, RollingHorizonConfig } from '../../shared/types';

export interface RunDialogProps {
  open: boolean;
  onClose: () => void;

  forceLp: boolean;
  dryRun: boolean;
  pathwayConfig: PathwayConfig;
  rollingConfig: RollingHorizonConfig;

  onForceLpChange: (v: boolean) => void;
  onDryRunChange: (v: boolean) => void;
  onPathwayConfigChange: (config: PathwayConfig) => void;
  onRollingConfigChange: (config: RollingHorizonConfig) => void;

  onRun: () => void;
}

export function RunDialog({
  open,
  onClose,
  forceLp,
  dryRun,
  pathwayConfig,
  rollingConfig,
  onForceLpChange,
  onDryRunChange,
  onPathwayConfigChange,
  onRollingConfigChange,
  onRun,
}: RunDialogProps) {
  if (!open) return null;

  const pathwayEnabled = pathwayConfig.enabled;
  const rollingEnabled = rollingConfig.enabled;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card run-config" onClick={(e) => e.stopPropagation()}>
        <div className="validation-report">
          <div className="validation-report-header">
            <div>
              <p className="eyebrow">Run</p>
              <h2>Run configuration</h2>
            </div>
          </div>

          <div className="validation-section">
            <p className="validation-section-title">Planning</p>
            <div className="sg-btn-row">
              <button
                className={`tb-btn${!pathwayEnabled ? '' : ' tb-btn--muted'}`}
                onClick={() => onPathwayConfigChange({ ...pathwayConfig, enabled: false, planningMode: 'single_period' })}
              >
                Single period
              </button>
              <button
                className={`tb-btn${pathwayEnabled ? '' : ' tb-btn--muted'}`}
                onClick={() => onPathwayConfigChange({
                  ...pathwayConfig,
                  enabled: true,
                  planningMode: 'pathway',
                  periods: pathwayConfig.periods.length
                    ? pathwayConfig.periods
                    : [
                      { period: 2030, objectiveWeight: 1, yearsWeight: 5 },
                      { period: 2040, objectiveWeight: 1, yearsWeight: 10 },
                    ],
                  selectedPeriod: pathwayConfig.selectedPeriod ?? 2030,
                })}
              >
                Pathway
              </button>
            </div>
          </div>

          <div className="validation-section">
            <p className="validation-section-title">Optimisation settings</p>
            <div className="sg-btn-row">
              <button
                className={`tb-btn${rollingEnabled ? '' : ' tb-btn--muted'}`}
                onClick={() => onRollingConfigChange({ ...rollingConfig, enabled: !rollingEnabled })}
              >
                Rolling horizon
              </button>
              <button
                className={`tb-btn${forceLp ? '' : ' tb-btn--muted'}`}
                onClick={() => onForceLpChange(!forceLp)}
              >
                Force LP
              </button>
              <button
                className={`tb-btn${dryRun ? '' : ' tb-btn--muted'}`}
                onClick={() => onDryRunChange(!dryRun)}
              >
                Dry run
              </button>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose}>Cancel</button>
          <button className="run-button" onClick={onRun}>
            {dryRun ? 'Validate' : 'Run model'}
          </button>
        </div>
      </div>
    </div>
  );
}
