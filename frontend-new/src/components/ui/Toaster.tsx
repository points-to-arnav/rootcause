import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import type { Toast } from '../../store/useAppStore';

const icons = {
  error: AlertCircle,
  success: CheckCircle2,
  info: Info,
} as const;

const tones: Record<Toast['tone'], string> = {
  error: 'text-down',
  success: 'text-up',
  info: 'text-accent',
};

export function Toaster() {
  const toasts = useAppStore((state) => state.toasts);
  const dismiss = useAppStore((state) => state.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-60 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
    >
      {toasts.map((toast) => {
        const Icon = icons[toast.tone];
        return (
          <div
            key={toast.id}
            role={toast.tone === 'error' ? 'alert' : 'status'}
            className="reveal pointer-events-auto flex items-start gap-2.5 rounded-lg border border-line-strong bg-overlay p-3 shadow-lg shadow-black/40"
          >
            <Icon className={`mt-0.5 size-4 shrink-0 ${tones[toast.tone]}`} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-ink">{toast.title}</p>
              {toast.body ? (
                <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{toast.body}</p>
              ) : null}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss"
              className="-m-1 rounded-md p-1 text-ink-3 transition-colors hover:bg-raised hover:text-ink"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
