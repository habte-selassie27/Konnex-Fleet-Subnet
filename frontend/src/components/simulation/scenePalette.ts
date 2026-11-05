// scenePalette — the WebGL twin of the CSS token set.
//
// Every colour the R3F scene uses comes from here so the 3D viewport flips with
// the same `theme` toggle as the rest of the dashboard. No hard-coded hex values
// inside mesh components (AGENTS.md §1.3 design-system rule).
import type { Theme } from '../../store/uiStore'

export interface ScenePalette {
  background: string
  floor: string
  gridFine: string
  gridSection: string
  gridFineOpacity: number
  gridSectionOpacity: number

  wall: string
  wallTrim: string

  shelfBody: string
  shelfEdge: string
  shelfLed: string

  crateBody: string
  crateAccent: string
  crateEdge: string

  binBody: string
  binInterior: string
  binRim: string

  cartBody: string
  cartDeck: string
  cartWheel: string
  cartAccent: string
  cartLidar: string

  ambientColor: string
  ambientIntensity: number
  keyColor: string
  keyIntensity: number
  rimColor: string
  rimIntensity: number

  fogColor: string
  fogNear: number
  fogFar: number

  headlightColor: string
  headlightIntensity: number

  ledIdle: string
  ledMoving: string
  ledCarrying: string
  ledWorking: string
}

export const SCENE_PALETTES: Record<Theme, ScenePalette> = {
  dark: {
    background: '#0a111c',
    floor: '#0b1220',
    gridFine: '#12384d',
    gridSection: '#00f3ff',
    gridFineOpacity: 0.5,
    gridSectionOpacity: 0.22,

    wall: '#0f172a',
    wallTrim: '#1e293b',

    shelfBody: '#243447',
    shelfEdge: '#3b4a5f',
    shelfLed: '#00f3ff',

    crateBody: '#334155',
    crateAccent: '#00f3ff',
    crateEdge: '#0b1220',

    binBody: '#0f172a',
    binInterior: '#060a12',
    binRim: '#10b981',

    cartBody: '#1e293b',
    cartDeck: '#334155',
    cartWheel: '#020617',
    cartAccent: '#00f3ff',
    cartLidar: '#0b1220',

    ambientColor: '#334155',
    ambientIntensity: 2.0,
    keyColor: '#ffffff',
    keyIntensity: 2.6,
    rimColor: '#38bdf8',
    rimIntensity: 0.6,

    fogColor: '#0a111c',
    fogNear: 46,
    fogFar: 100,

    headlightColor: '#cfefff',
    headlightIntensity: 5,

    ledIdle: '#94a3b8',
    ledMoving: '#00f3ff',
    ledCarrying: '#10b981',
    ledWorking: '#f59e0b',
  },

  light: {
    background: '#e7eef7',
    floor: '#eef3f9',
    gridFine: '#c3d2e3',
    gridSection: '#7c9ab8',
    gridFineOpacity: 0.8,
    gridSectionOpacity: 0.55,

    wall: '#cbd5e1',
    wallTrim: '#e2e8f0',

    shelfBody: '#b8c6d6',
    shelfEdge: '#94a3b8',
    shelfLed: '#0284c7',

    crateBody: '#64748b',
    crateAccent: '#0284c7',
    crateEdge: '#475569',

    binBody: '#94a3b8',
    binInterior: '#b9c6d4',
    binRim: '#059669',

    cartBody: '#475569',
    cartDeck: '#334155',
    cartWheel: '#1e293b',
    cartAccent: '#0284c7',
    cartLidar: '#334155',

    ambientColor: '#ffffff',
    ambientIntensity: 1.1,
    keyColor: '#ffffff',
    keyIntensity: 2.6,
    rimColor: '#38bdf8',
    rimIntensity: 0.35,

    fogColor: '#e7eef7',
    fogNear: 48,
    fogFar: 110,

    headlightColor: '#ffffff',
    headlightIntensity: 0.6,

    ledIdle: '#64748b',
    ledMoving: '#0284c7',
    ledCarrying: '#059669',
    ledWorking: '#d97706',
  },
}

/** LED colour for a cart's current nav state. */
export function ledColorFor(palette: ScenePalette, navState: string): string {
  switch (navState) {
    case 'moving_to_cargo':
    case 'moving_to_depot':
      return palette.ledMoving
    case 'picking_up':
    case 'depositing_stack':
      return palette.ledWorking
    case 'charging':
      return palette.ledWorking
    default:
      return palette.ledIdle
  }
}
