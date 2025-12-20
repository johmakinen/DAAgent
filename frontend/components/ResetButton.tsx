import { Button } from "@/components/ui/button";

interface ResetButtonProps {
  onReset: () => void;
  disabled?: boolean;
}

export default function ResetButton({ onReset, disabled }: ResetButtonProps) {
  return (
    <Button
      onClick={onReset}
      disabled={disabled}
      variant="destructive"
      size="sm"
    >
      Reset History
    </Button>
  );
}

