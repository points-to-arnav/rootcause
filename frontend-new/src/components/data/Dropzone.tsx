import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import clsx from 'clsx';
import { FileSpreadsheet, Upload } from 'lucide-react';
import { Button } from '../ui/Button';

/** The formats the ingestion loader reads. Anything else is refused here, before
 *  it costs an upload, with a message that names the file. */
const ACCEPTED_EXTENSIONS = ['.xlsx', '.xls', '.csv', '.tsv'];

function hasAcceptedExtension(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension));
}

function skippedMessage(skipped: File[]): string {
  const names = skipped.map((file) => file.name).join(', ');
  return `${names} ${skipped.length === 1 ? 'was' : 'were'} skipped. Only Excel and CSV files can be read.`;
}

interface DropzoneProps {
  onFiles: (files: File[]) => void | Promise<void>;
  onLoadSample: () => void | Promise<void>;
  /** True while a dataset is being read; the controls lock so it cannot be
   *  started twice. */
  busy?: boolean;
  /** A single row, for replacing data that is already loaded. */
  compact?: boolean;
}

export function Dropzone({ onFiles, onLoadSample, busy = false, compact = false }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  // Entering a child element fires dragleave on its parent, so a bare boolean
  // flickers. Counting enters against leaves keeps the highlight steady.
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  function handle(list: FileList | null) {
    if (busy || !list || list.length === 0) return;

    const files = Array.from(list);
    const accepted = files.filter(hasAcceptedExtension);
    const skipped = files.filter((file) => !hasAcceptedExtension(file));

    setNotice(skipped.length > 0 ? skippedMessage(skipped) : null);
    if (accepted.length > 0) void onFiles(accepted);
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    handle(event.target.files);
    // Without this, choosing the same file twice in a row fires no change event.
    event.target.value = '';
  }

  function onDragEnter(event: DragEvent<HTMLDivElement>) {
    if (!event.dataTransfer.types.includes('Files')) return;
    event.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    // Cancelling dragover is what marks this element as a valid drop target.
    if (event.dataTransfer.types.includes('Files')) event.preventDefault();
  }

  function onDragLeave() {
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    handle(event.dataTransfer.files);
  }

  const chooseButton = (
    <Button
      variant="primary"
      size={compact ? 'sm' : 'md'}
      loading={busy}
      onClick={() => inputRef.current?.click()}
    >
      {busy ? 'Reading your data…' : 'Choose files'}
    </Button>
  );

  const sampleButton = (
    <Button size={compact ? 'sm' : 'md'} disabled={busy} onClick={() => void onLoadSample()}>
      Use the sample retail data
    </Button>
  );

  return (
    <div>
      <div
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={clsx(
          'rounded-lg border border-dashed transition-colors',
          dragging ? 'border-accent bg-accent/8' : 'border-line-strong bg-surface',
          compact
            ? 'flex flex-wrap items-center gap-3 px-4 py-3'
            : 'flex flex-col items-center px-6 py-12 text-center',
        )}
      >
        {compact ? (
          <>
            <Upload className="size-4 shrink-0 text-ink-2" aria-hidden="true" />
            <p className="min-w-0 flex-1 text-[13px] text-ink-2">
              Drop Excel or CSV files here to replace the current data.
            </p>
            <div className="flex items-center gap-2">
              {chooseButton}
              {sampleButton}
            </div>
          </>
        ) : (
          <>
            <span className="flex size-10 items-center justify-center rounded-md border border-line bg-raised text-ink-2">
              <FileSpreadsheet className="size-5" aria-hidden="true" />
            </span>
            <h3 className="mt-4 text-[16px] font-semibold text-ink">
              {dragging ? 'Release to load these files' : 'Drop your files here'}
            </h3>
            <p className="mt-1.5 max-w-sm text-[13px] leading-5 text-ink-2">
              Excel workbooks or CSV files. Load several together and each sheet becomes a table
              you can ask about.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {chooseButton}
              {sampleButton}
            </div>
            <p className="mt-4 font-mono text-[12px] text-ink-3">
              {ACCEPTED_EXTENSIONS.join('  ·  ')}
            </p>
          </>
        )}
      </div>

      {notice ? (
        <p role="alert" className="mt-2.5 text-[13px] text-down">
          {notice}
        </p>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS.join(',')}
        onChange={onInputChange}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      />
    </div>
  );
}
