import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type ProfileInput, unwrap } from "@/shared/api"
import { useLocale } from "@/shared/i18n"

export const PROFILE_KEY = ["candidate", "profile"] as const
const GRADE_HINT_KEY = ["candidate", "grade-hint"] as const
const PDF_FALLBACK = "profile.pdf"
const ENCODED_NAME = /filename\*=UTF-8''([^;]+)/i

export function useProfile() {
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/profile")),
  })
}

export function useSaveProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: ProfileInput) => unwrap(api.PUT("/api/candidate/profile", { body: input })),
    onSuccess: async (profile) => {
      client.setQueryData(PROFILE_KEY, profile)
      await client.invalidateQueries({ queryKey: GRADE_HINT_KEY })
    },
  })
}

export function useParseResume() {
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(
        api.POST("/api/candidate/profile/resume", {
          body: "",
          bodySerializer: () => file,
          headers: { "Content-Type": "application/pdf" },
        }),
      ),
  })
}

function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url))
}

function fileNameOf(disposition: string | null): string {
  const encoded = disposition === null ? undefined : ENCODED_NAME.exec(disposition)?.[1]
  return encoded === undefined ? PDF_FALLBACK : decodeURIComponent(encoded)
}

export function useDownloadProfilePdf() {
  const { locale } = useLocale()
  return useMutation({
    mutationFn: async () => {
      const result = await api.GET("/api/candidate/profile/pdf", {
        params: { query: { lang: locale } },
        parseAs: "blob",
      })
      const blob = await unwrap(Promise.resolve(result))
      saveBlob(blob as Blob, fileNameOf(result.response.headers.get("Content-Disposition")))
    },
  })
}
