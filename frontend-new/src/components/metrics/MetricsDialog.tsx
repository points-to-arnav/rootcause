import { useAppStore } from '../../store/useAppStore';
import { Modal } from '../ui/Modal';
import { CacheMetrics } from './CacheMetrics';

export function MetricsDialog() {
  const open = useAppStore((state) => state.metricsOpen);
  const setOpen = useAppStore((state) => state.setMetricsOpen);

  return (
    <Modal
      open={open}
      onClose={() => setOpen(false)}
      size="lg"
      title="Prompt cache"
      description="What each answer cost to plan and narrate, and how much the cache paid back."
    >
      <CacheMetrics />
    </Modal>
  );
}
