interface ResetButtonProps {
  onReset: () => void;
  disabled?: boolean;
}

export default function ResetButton({ onReset, disabled }: ResetButtonProps) {
  return (
    <button
      onClick={onReset}
      disabled={disabled}
      className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed dark:border-red-700 dark:bg-gray-800 dark:text-red-400 dark:hover:bg-gray-700"
    >
      Reset History
    </button>
  );
}

