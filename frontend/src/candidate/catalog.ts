import { useEffect, useState } from 'react'
import { api, type Grade, type Industry, type Specialization } from '../api/client'

export type Catalog = {
  grades: Grade[]
  industries: Industry[]
  specializations: Specialization[]
}

/** Справочники для пути кандидата; `null`, пока не загрузились. */
export function useCatalog(): { catalog: Catalog | null; failed: boolean } {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    Promise.all([
      api.GET('/api/catalog/grades'),
      api.GET('/api/catalog/industries'),
      api.GET('/api/catalog/specializations'),
    ]).then(([grades, industries, specializations]) => {
      if (grades.data && industries.data && specializations.data) {
        setCatalog({
          grades: grades.data,
          industries: industries.data,
          specializations: specializations.data,
        })
      } else {
        setFailed(true)
      }
    })
  }, [])

  return { catalog, failed }
}

export function gradeName(catalog: Catalog, code: string): string {
  return catalog.grades.find((g) => g.code === code)?.name ?? code
}
