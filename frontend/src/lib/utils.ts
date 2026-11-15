import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getSafeExternalUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null

  try {
    const url = new URL(value.trim())
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null
  } catch {
    return null
  }
}

