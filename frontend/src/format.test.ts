import { describe, expect, it } from 'vitest'
import { formatAge, formatForeign, formatSpecialty } from './format'

describe('squad display formatting', () => {
  it('formats exact Hattrick age as years and days', () => {
    expect(formatAge(18, 43)).toBe('18y 43d')
  })

  it('keeps unknown fields explicit', () => {
    expect(formatForeign(null)).toBe('Unknown')
    expect(formatSpecialty(null)).toBe('Unknown')
  })
})
