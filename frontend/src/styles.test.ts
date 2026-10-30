import { describe, expect, it } from 'vitest'
import { DAYLIGHT_TOKENS } from './visualTheme'

describe('bright naked-eye 3D art direction', () => {
  it('keeps the original photograph luminous', () => {
    expect(DAYLIGHT_TOKENS.sceneExposure).toBe(1.08)
    expect(DAYLIGHT_TOKENS.sceneSaturation).toBe(.92)
  })

  it('uses daylight glass instead of opaque black panels', () => {
    expect(DAYLIGHT_TOKENS.glass).toBe('rgba(247,245,238,.72)')
    expect(DAYLIGHT_TOKENS.ink).toBe('#202522')
  })
})
