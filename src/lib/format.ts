export function formatNumber(value: number | undefined, digits = 2) {
  if (value === undefined || Number.isNaN(value)) {
    return "0.00";
  }

  return value.toFixed(digits);
}

export function formatPercent(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return "0%";
  }

  return `${(value * 100).toFixed(0)}%`;
}

export function formatTarget(value: string | null | undefined) {
  return value ?? "System";
}
