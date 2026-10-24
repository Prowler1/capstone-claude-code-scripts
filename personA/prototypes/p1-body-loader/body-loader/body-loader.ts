import type Backend from '../backend'
import { drawnFilesOf } from '../drawn-files-of'
import type Git from '../git'
import PaneState from '../pane-state'

/** What the loader reads and writes of the pane it loads for. */
export interface BodyLoaderDeps {
  readonly modelOf: () => PaneState.PaneModel
  readonly setModel: (model: PaneState.PaneModel) => void
  readonly backendOf: () => Backend.Backend | null
  readonly generationOf: () => number
}

/** The hunk bodies of the drawn files, each read once per stamp. */
export interface BodyLoader {
  /**
   * @param redraw asks the pane to draw again once bodies change
   * @returns whether a drawn file's hunks failed to read
   */
  readonly load: (redraw: () => void) => Promise<boolean>
  readonly reset: () => void
}

/**
 * A loader of the drawn files' hunk bodies: the stamp they were read under,
 * the base they belong to, and the paths already asked for.
 *
 * @param deps the pane's model, backend and generation
 * @returns the loader
 */
export function bodyLoaderOf(deps: BodyLoaderDeps): BodyLoader {
  let stamp: string | null = null
  let base: string | null = null

  const asked = new Set<string>()

  const stampOf = (data: Git.DiffData) =>
    `${deps.generationOf()}|${data.baseRef}`

  function reset() {
    stamp = null
    base = null
    asked.clear()
  }

  async function fetch(
    pinned: Backend.Backend,
    data: Git.DiffData,
    redraw: () => void,
  ): Promise<boolean> {
    const at = stampOf(data)

    const files = drawnFilesOf(deps.modelOf()).filter(
      file => !asked.has(file.path),
    )

    for (const file of files) {
      asked.add(file.path)
    }

    const read = await pinned.fetchHunks(data, files)
    const isCurrent = stamp === at && read.size > 0

    if (isCurrent) {
      const model = deps.modelOf()

      deps.setModel({ ...model, bodies: new Map([...model.bodies, ...read]) })
      redraw()
    }

    return [...read.values()].includes(null)
  }

  async function load(redraw: () => void): Promise<boolean> {
    const { data } = deps.modelOf()
    const pinned = deps.backendOf()

    if (!data || !pinned) {
      reset()
      deps.setModel({ ...deps.modelOf(), bodies: PaneState.NO_BODIES })

      return false
    }

    const at = stampOf(data)

    if (at !== stamp) {
      stamp = at
      asked.clear()
    }

    if (data.baseRef !== base) {
      base = data.baseRef
      deps.setModel({ ...deps.modelOf(), bodies: PaneState.NO_BODIES })
      redraw()
    }

    return fetch(pinned, data, redraw)
  }

  return { load, reset }
}
