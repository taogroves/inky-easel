const OFFSET_RE = /(Z|[+-]\d{2}:?\d{2})$/i;

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function parseApiDate(iso: string): Date {
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(iso) && !OFFSET_RE.test(iso) ? `${iso}Z` : iso;
  return new Date(normalized);
}

export function formatDateTime(iso: string | null, timeZone?: string | null): string {
  if (!iso) return "never";
  const date = parseApiDate(iso);
  const options: Intl.DateTimeFormatOptions = {
    dateStyle: "medium",
    timeStyle: "short",
    ...(timeZone ? { timeZone } : {}),
  };
  try {
    return new Intl.DateTimeFormat(undefined, options).format(date);
  } catch {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(date);
  }
}
