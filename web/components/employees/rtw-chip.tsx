import { StatusChip } from "@/components/ui/status-chip";
import { RTW_LABEL, RTW_TONE, type RTWStatus } from "@/lib/employees/rtw";
export function RTWChip({ status = "not_recorded" }: { status?: RTWStatus }) {
  return (
    <StatusChip tone={RTW_TONE[status]}>
      <span>
        <span className="sr-only">Right to Work: </span>
        {RTW_LABEL[status]}
      </span>
    </StatusChip>
  );
}
