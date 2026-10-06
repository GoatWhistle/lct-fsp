import { useEffect, useState } from 'react'
import { api, type Grade, type Specialization, type Technology } from '../api/client'

export type EmployerCatalog = {
  grades: Grade[]
  specializations: Specialization[]
  technologies: Technology[]
}

/** Справочники для формы потребности; `null`, пока не загрузились. */
export function useEmployerCatalog(): { catalog: EmployerCatalog | null; failed: boolean } {
  const [catalog, setCatalog] = useState<EmployerCatalog | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    Promise.all([
      api.GET('/api/catalog/grades'),
      api.GET('/api/catalog/specializations'),
      api.GET('/api/catalog/technologies'),
    ]).then(([grades, specializations, technologies]) => {
      if (grades.data && specializations.data && technologies.data) {
        setCatalog({
          grades: grades.data,
          specializations: specializations.data,
          technologies: technologies.data,
        })
      } else {
        setFailed(true)
      }
    })
  }, [])

  return { catalog, failed }
}
