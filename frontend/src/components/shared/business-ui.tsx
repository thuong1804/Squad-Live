import { useMutation, useQueryClient } from "@tanstack/react-query";
import { errorMessage, ApiError } from "@/lib/api-client";
import { statusPresentation } from "@/lib/status";
import { Button } from "@/components/ui/button";
export function Status({ value }: { value: string }): React.JSX.Element {
  const [label, variant] = statusPresentation(value);
  return <span className={`status-badge status-${variant}`}>{label}</span>;
}
export function Pagination({
  offset,
  count,
  onChange,
}: {
  offset: number;
  count: number;
  onChange: (n: number) => void;
}): React.JSX.Element {
  return (
    <nav className="pagination" aria-label="Phân trang">
      <Button
        variant="outline"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - 25))}
      >
        Trang trước
      </Button>
      <span>Trang {offset / 25 + 1}</span>
      <Button
        variant="outline"
        disabled={count < 25}
        onClick={() => onChange(offset + 25)}
      >
        Trang sau
      </Button>
    </nav>
  );
}
export function ErrorNotice({
  error,
}: {
  error: unknown;
}): React.JSX.Element | null {
  return error ? (
    <p role="alert" className="error-notice">
      {errorMessage(error)}
    </p>
  ) : null;
}
export function useCommand<T, V>(
  mutationFn: (value: V) => Promise<T>,
  onSuccess?: (data: T) => void,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async (data) => {
      await client.invalidateQueries();
      onSuccess?.(data);
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409)
        await client.invalidateQueries();
    },
  });
}
export const timeLabel = (value: string | null): string =>
  value ? new Date(value).toLocaleString("vi-VN") : "—";
