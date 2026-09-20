import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Button } from './Button';

interface CopyButtonProps {
  value: string;
  label?: string;
}

export function CopyButton({ value, label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timer);
  }, [copied]);

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
        } catch {
          setCopied(false);
        }
      }}
      icon={
        copied ? (
          <Check className="size-3.5 text-up" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5" aria-hidden="true" />
        )
      }
    >
      {copied ? 'Copied' : label}
    </Button>
  );
}
