import { useEffect } from 'react'
import { useResourceStore } from './resourceStore'

export function useResources() {
  const resources = useResourceStore((s) => s.resources)
  const uploads = useResourceStore((s) => s.uploads)
  const load = useResourceStore((s) => s.load)
  const upload = useResourceStore((s) => s.upload)
  const remove = useResourceStore((s) => s.remove)

  useEffect(() => {
    void load()
  }, [load])

  return { resources, uploads, upload, remove }
}
