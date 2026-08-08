export function formatAge(years: number, days: number): string {
  return `${years}y ${days}d`
}

export function formatNumber(value: number | null): string {
  return value === null ? '—' : value.toLocaleString()
}

export function formatForeign(value: boolean | null): string {
  if (value === null) return 'Unknown'
  return value ? 'Yes' : 'No'
}

export function formatSpecialty(value: number | null): string {
  if (value === null) return 'Unknown'
  return value === 0 ? 'None' : `Code ${value}`
}

export function formatSyncTime(value: string | null): string {
  if (!value) return 'Not synced yet'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
