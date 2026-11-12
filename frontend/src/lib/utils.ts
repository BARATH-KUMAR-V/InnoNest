import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function inr(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (compact && Math.abs(value) >= 1e7) return `INR ${(value / 1e7).toFixed(2)} Cr`;
  if (compact && Math.abs(value) >= 1e5) return `INR ${(value / 1e5).toFixed(2)} L`;
  return "INR " + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value);
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value.endsWith("Z") ? value : value + "Z").toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function dateOnly(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value.length === 10 ? value + "T00:00:00" : value.endsWith("Z") ? value : value + "Z").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "-";
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

const documentLabels: Record<string, string> = {
  PAN: "PAN card", ADDRESS_PROOF: "Address proof", IDENTITY_PROOF: "Identity proof", SALARY_SLIP: "Latest salary slip", BANK_STATEMENT: "Bank statement (last 6 months)",
  FORM16: "Form 16", ITR: "Income tax return", GST_RETURN: "GST return summary", BUSINESS_FINANCIALS: "Business financial statements", SALE_AGREEMENT: "Agreement for sale",
  SALE_DEED: "Sale deed or title deed", ENCUMBRANCE_CERTIFICATE: "Encumbrance certificate", VALUATION_REPORT: "Property valuation report", LEGAL_REPORT: "Legal opinion report",
  TECHNICAL_REPORT: "Technical inspection report",
};

export function docLabel(value: string | null | undefined): string {
  if (!value) return "-";
  return documentLabels[value] ?? titleCase(value);
}
