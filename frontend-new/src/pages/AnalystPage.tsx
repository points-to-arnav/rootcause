import { useEffect, useRef } from 'react';
import { AlertCircle, MessageSquareText, RotateCcw } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { AppShell } from '../components/layout/AppShell';
import { AnswerPanel } from '../components/analyst/AnswerPanel';
import { Composer } from '../components/analyst/Composer';
import { Suggestions } from '../components/analyst/Suggestions';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { Spinner } from '../components/ui/Spinner';
import { starterQuestions } from '../lib/starters';
import { CacheBadge } from '../components/metrics/CacheBadge';

export function AnalystPage() {
  const messages = useAppStore((state) => state.messages);
  const asking = useAppStore((state) => state.asking);
  const ask = useAppStore((state) => state.ask);
  const retryLast = useAppStore((state) => state.retryLast);
  const datasetId = useAppStore((state) => state.datasetId);
  const semantic = useAppStore((state) => state.semantic);
  const setTab = useAppStore((state) => state.setTab);

  const bottomRef = useRef<HTMLDivElement>(null);
  const starters = starterQuestions(semantic);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, asking]);

  if (!datasetId) {
    return (
      <AppShell title="Ask" description="Questions answered against your data">
        <EmptyState
          icon={MessageSquareText}
          title="Load a dataset to start asking"
          body="RootCause answers from data you provide and shows the SQL behind every number."
          actions={
            <Button variant="primary" onClick={() => setTab('data')}>
              Go to Data
            </Button>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Ask"
      description="Questions answered against your data"
      actions={<CacheBadge />}
      fillHeight
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-4 py-6">
          {messages.length === 0 ? (
            <div className="pt-6">
              <h2 className="text-[20px] font-semibold tracking-tight text-ink">
                What would you like to know?
              </h2>
              <p className="mt-1 max-w-prose text-[14px] leading-6 text-ink-2">
                Ask in plain language. Every answer comes with the query that produced it, the
                time range it used, and any data problems that affect it.
              </p>
              {starters.length > 0 ? (
                <ul className="mt-5 max-w-xl divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
                  {starters.map((question) => (
                    <li key={question}>
                      <button
                        onClick={() => ask(question)}
                        className="w-full px-3.5 py-2.5 text-left text-[14px] text-ink-2 transition-colors hover:bg-raised hover:text-ink"
                      >
                        {question}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message) =>
                message.sender === 'user' ? (
                  <div key={message.id}>
                    <p className="text-[12px] text-ink-3">You · {message.timestamp}</p>
                    <p className="mt-0.5 max-w-[68ch] text-[16px] font-medium leading-7 text-ink">
                      {message.text}
                    </p>
                  </div>
                ) : message.failed ? (
                  <div
                    key={message.id}
                    role="alert"
                    className="rounded-lg border border-down/30 bg-down/8 p-4"
                  >
                    <div className="flex gap-2.5">
                      <AlertCircle
                        className="mt-0.5 size-4 shrink-0 text-down"
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-[14px] font-medium text-ink">
                          That question could not be answered
                        </p>
                        <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{message.text}</p>
                        <Button
                          size="sm"
                          className="mt-2.5"
                          onClick={retryLast}
                          icon={<RotateCcw className="size-3.5" aria-hidden="true" />}
                        >
                          Try again
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : message.response ? (
                  <AnswerPanel key={message.id} response={message.response} onAsk={ask} />
                ) : (
                  <p key={message.id} className="max-w-[68ch] text-[14px] leading-6 text-ink">
                    {message.text}
                  </p>
                ),
              )}

              {asking ? (
                <div
                  role="status"
                  className="flex items-center gap-2.5 rounded-lg border border-line bg-surface px-4 py-3 text-[13px] text-ink-2"
                >
                  <Spinner size={14} />
                  Planning the query and running it against your data
                </div>
              ) : null}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-line bg-ground px-4 py-3">
        <div className="mx-auto w-full max-w-4xl space-y-2">
          <Composer onSubmit={ask} busy={asking} />
          {messages.length > 0 && starters.length > 0 && !asking ? (
            <Suggestions suggestions={starters.slice(0, 3)} onSelect={ask} label="Try" />
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}
