const percentFormatters = new Map<number, Intl.NumberFormat>();
const decimalFormatters = new Map<number, Intl.NumberFormat>();
const integerFormatter = new Intl.NumberFormat("fr-FR");
const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function percentFormatter(digits: number): Intl.NumberFormat {
  const cached = percentFormatters.get(digits);
  if (cached) {
    return cached;
  }
  const formatter = new Intl.NumberFormat("fr-FR", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  percentFormatters.set(digits, formatter);
  return formatter;
}

function decimalFormatter(digits: number): Intl.NumberFormat {
  const cached = decimalFormatters.get(digits);
  if (cached) {
    return cached;
  }
  const formatter = new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  decimalFormatters.set(digits, formatter);
  return formatter;
}

export function formatPercent(value: number, digits = 1): string {
  return percentFormatter(digits).format(value);
}

export function formatDecimal(value: number, digits = 3): string {
  return decimalFormatter(digits).format(value);
}

export function formatSigned(value: number, digits = 3): string {
  const formatted = decimalFormatter(digits).format(Math.abs(value));
  if (value > 0) {
    return `+${formatted}`;
  }
  return value < 0 ? `−${formatted}` : formatted;
}

export function formatPoints(value: number, digits = 1): string {
  return `${formatSigned(value * 100, digits)} pts`;
}

export function formatInteger(value: number): string {
  return integerFormatter.format(value);
}

export function formatDate(isoDate: string): string {
  return dateFormatter.format(new Date(`${isoDate}T00:00:00Z`));
}
