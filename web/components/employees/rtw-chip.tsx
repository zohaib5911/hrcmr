import { StatusChip } from "@/components/ui/status-chip";
import { RTW_LABEL, RTW_TONE, type RTWStatus } from "@/lib/employees/rtw";
export function RTWChip({ status = "not_recorded" }: { status?: RTWStatus }) {
  return (
    <StatusChip tone={RTW_TONE[status]} aria-label={"Right to Work: " + RTW_LABEL[status]}>
      {RTW_LABEL[status]}
    </StatusChip>
  );
}
