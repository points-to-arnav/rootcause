import { useState } from 'react';
import clsx from 'clsx';
import { Check } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { providerModelField } from '../../types';
import type { AppSettings, Provider } from '../../types';

export function SettingsDialog() {
  const open = useAppStore((state) => state.settingsOpen);
  const setOpen = useAppStore((state) => state.setSettingsOpen);
  const settings = useAppStore((state) => state.settings);

  return (
    <Modal
      open={open}
      onClose={() => setOpen(false)}
      title="Model"
      description="Which language model turns your question into a query."
    >
      {/* Mounted only while open, so the form always starts from what the
          server currently has and a cancelled edit never lingers. */}
      {settings ? (
        <SettingsForm settings={settings} onDone={() => setOpen(false)} />
      ) : (
        <p className="text-[13px] text-ink-2">
          Model settings are unavailable because the server did not respond.
        </p>
      )}
    </Modal>
  );
}

function SettingsForm({ settings, onDone }: { settings: AppSettings; onDone: () => void }) {
  const saveSettings = useAppStore((state) => state.saveSettings);
  const toast = useAppStore((state) => state.toast);

  const [provider, setProvider] = useState<Provider>(settings.active_provider);
  const [models, setModels] = useState<Record<Provider, string>>({
    openrouter: settings.openrouter_model,
    nvidia_nim: settings.nvidia_nim_model,
    claude_code: settings.claude_code_model,
    anthropic: settings.anthropic_model,
  });
  const [caching, setCaching] = useState(settings.prompt_caching_enabled);
  const [saving, setSaving] = useState(false);

  const selected = settings.providers.find((candidate) => candidate.id === provider);

  async function save() {
    setSaving(true);
    try {
      await saveSettings({
        active_provider: provider,
        [providerModelField[provider]]: models[provider].trim(),
        prompt_caching_enabled: caching,
      });
      toast({ tone: 'success', title: 'Model settings saved' });
      onDone();
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Settings not saved',
        body: error instanceof Error ? error.message : 'The server rejected the change.',
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-[13px] font-medium text-ink">Provider</legend>
        <div className="space-y-1.5">
          {settings.providers.map((option) => {
            const active = provider === option.id;
            return (
              <button
                key={option.id}
                data-autofocus={active ? '' : undefined}
                onClick={() => setProvider(option.id)}
                aria-pressed={active}
                className={clsx(
                  'flex w-full items-start gap-2.5 rounded-md border p-2.5 text-left transition-colors',
                  active
                    ? 'border-accent/50 bg-accent/8'
                    : 'border-line bg-raised hover:border-line-strong',
                )}
              >
                <span
                  className={clsx(
                    'mt-1 size-1.5 shrink-0 rounded-full',
                    option.available ? 'bg-up' : 'bg-ink-3',
                  )}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium text-ink">{option.label}</span>
                    {active ? (
                      <Check className="size-3.5 shrink-0 text-accent" aria-hidden="true" />
                    ) : null}
                  </span>
                  <span className="mt-0.5 block text-[12px] leading-4 text-ink-3">
                    {option.available ? 'Ready to use' : `Needs ${option.requires}`}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div>
        <label htmlFor="model-name" className="block text-[13px] font-medium text-ink">
          Model for {selected?.label ?? 'this provider'}
        </label>
        <input
          id="model-name"
          type="text"
          spellCheck={false}
          autoComplete="off"
          value={models[provider]}
          onChange={(event) =>
            setModels((current) => ({ ...current, [provider]: event.target.value }))
          }
          className="mt-1 h-9 w-full rounded-md border border-line bg-ground px-2.5 font-mono text-[13px] text-ink outline-none transition-colors focus:border-accent"
        />
      </div>

      <label className="flex items-start gap-2.5">
        <input
          type="checkbox"
          checked={caching}
          onChange={(event) => setCaching(event.target.checked)}
          className="mt-0.5 size-3.5 accent-[var(--color-accent)]"
        />
        <span>
          <span className="block text-[13px] font-medium text-ink">Reuse cached prompts</span>
          <span className="block text-[12px] leading-4 text-ink-3">
            {selected?.supports_caching
              ? 'Repeat questions cost less and answer faster.'
              : 'This provider ignores the setting.'}
          </span>
        </span>
      </label>

      <p className="border-t border-line pt-3 text-[13px] leading-5 text-ink-3">
        If the chosen provider is rate-limited or times out, RootCause falls back to another one
        for that request.
      </p>

      <div className="flex items-center justify-end gap-2 border-t border-line pt-3">
        <Button onClick={onDone}>Cancel</Button>
        <Button variant="primary" loading={saving} onClick={save}>
          Save
        </Button>
      </div>
    </div>
  );
}
