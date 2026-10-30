import { describe, expect, it } from 'vitest'
import { getLayerShift, getSceneTransform, normalizePointer } from './DepthBackground'

describe('3D background parallax', () => {
  it('moves near layers farther than distant layers', () => {
    const far = getLayerShift(1, 0.5, 0, false)
    const near = getLayerShift(1, 0.5, 3, false)

    expect(near.x).toBeGreaterThan(far.x * 4)
    expect(near.y).toBeGreaterThan(far.y * 4)
  })

  it('boosts depth motion while the visual agent is working', () => {
    const idle = getLayerShift(0.8, 0.4, 2, false)
    const active = getLayerShift(0.8, 0.4, 2, true)

    expect(active.x).toBeGreaterThan(idle.x)
    expect(active.y).toBeGreaterThan(idle.y)
  })

  it('normalizes window pointer coordinates for global mouse tracking', () => {
    expect(normalizePointer(0, 0, 1000, 500)).toEqual({ x:-1, y:1 })
    expect(normalizePointer(500, 250, 1000, 500)).toEqual({ x:0, y:0 })
    expect(normalizePointer(1000, 500, 1000, 500)).toEqual({ x:1, y:-1 })
  })

  it('tilts the stage toward the viewer without excessive rotation', () => {
    expect(getSceneTransform(1, -1, false)).toEqual({ rotateX:-2.4, rotateY:3.8, translateX:8, translateY:5 })
  })

  it('amplifies the stage response while analysis is active', () => {
    const idle = getSceneTransform(.5, .5, false)
    const active = getSceneTransform(.5, .5, true)

    expect(active.rotateX).toBeGreaterThan(idle.rotateX)
    expect(active.rotateY).toBeGreaterThan(idle.rotateY)
    expect(active.translateX).toBeGreaterThan(idle.translateX)
  })
})
