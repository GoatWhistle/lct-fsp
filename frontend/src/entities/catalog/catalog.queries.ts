import { useQuery } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"

const FOREVER = Number.POSITIVE_INFINITY

export function useGrades() {
  return useQuery({
    queryKey: ["catalog", "grades"],
    queryFn: () => unwrap(api.GET("/api/catalog/grades")),
    staleTime: FOREVER,
  })
}

export function useSpecializations() {
  return useQuery({
    queryKey: ["catalog", "specializations"],
    queryFn: () => unwrap(api.GET("/api/catalog/specializations")),
    staleTime: FOREVER,
  })
}

export function useTechnologies() {
  return useQuery({
    queryKey: ["catalog", "technologies"],
    queryFn: () => unwrap(api.GET("/api/catalog/technologies")),
    staleTime: FOREVER,
  })
}

export function useIndustries() {
  return useQuery({
    queryKey: ["catalog", "industries"],
    queryFn: () => unwrap(api.GET("/api/catalog/industries")),
    staleTime: FOREVER,
  })
}
