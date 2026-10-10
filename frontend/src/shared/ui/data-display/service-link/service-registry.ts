export type ServiceId =
  | "github"
  | "gitlab"
  | "bitbucket"
  | "gitea"
  | "sourcehut"
  | "telegram"
  | "discord"
  | "linkedin"
  | "x"
  | "mastodon"
  | "bluesky"
  | "youtube"
  | "twitch"
  | "instagram"
  | "facebook"
  | "threads"
  | "reddit"
  | "medium"
  | "vk"
  | "stackOverflow"
  | "leetcode"
  | "codeforces"
  | "figma"
  | "behance"
  | "dribbble"
  | "notion"
  | "npm"
  | "vimeo"
  | "soundcloud"
  | "spotify"
  | "boosty"
  | "patreon"
  | "tiktok"
  | "hackerone"
  | "kaggle"
  | "huggingface"
  | "devpost"
  | "dockerHub"
  | "pypi"
  | "cratesIo"
  | "goDev"
  | "codepen"
  | "devTo"
  | "hashnode"
  | "habr"
  | "stepik"
  | "coursera"
  | "artstation"
  | "itch"
  | "steam"
  | "googleScholar"
  | "orcid"
  | "researchGate"
  | "substack"
  | "goodreads"
  | "lastfm"
  | "pinterest"
  | "whatsapp"
  | "signal"
  | "matrix"
  | "keybase"
  | "codewars"
  | "hackerrank"
  | "kickstarter"
  | "ycombinator"
  | "producthunt"

export type ServiceDefinition = {
  id: ServiceId
  label: string
  domains: readonly string[]
}

export const SERVICES: readonly ServiceDefinition[] = [
  { id: "github", label: "GitHub", domains: ["github.com", "github.io", "gist.github.com"] },
  { id: "gitlab", label: "GitLab", domains: ["gitlab.com", "gitlab.io"] },
  { id: "bitbucket", label: "Bitbucket", domains: ["bitbucket.org"] },
  { id: "gitea", label: "Gitea", domains: ["gitea.com", "gitea.io"] },
  { id: "sourcehut", label: "SourceHut", domains: ["sr.ht"] },
  { id: "telegram", label: "Telegram", domains: ["t.me", "telegram.me", "telegram.org"] },
  { id: "discord", label: "Discord", domains: ["discord.com", "discord.gg", "discordapp.com"] },
  { id: "linkedin", label: "LinkedIn", domains: ["linkedin.com", "lnkd.in"] },
  { id: "x", label: "X", domains: ["x.com", "twitter.com", "t.co"] },
  {
    id: "mastodon",
    label: "Mastodon",
    domains: ["mastodon.social", "mastodon.online", "mstdn.social"],
  },
  { id: "bluesky", label: "Bluesky", domains: ["bsky.app", "bsky.social"] },
  { id: "youtube", label: "YouTube", domains: ["youtube.com", "youtu.be"] },
  { id: "twitch", label: "Twitch", domains: ["twitch.tv"] },
  { id: "instagram", label: "Instagram", domains: ["instagram.com"] },
  { id: "facebook", label: "Facebook", domains: ["facebook.com", "fb.com"] },
  { id: "threads", label: "Threads", domains: ["threads.net", "threads.com"] },
  { id: "reddit", label: "Reddit", domains: ["reddit.com", "redd.it"] },
  { id: "medium", label: "Medium", domains: ["medium.com"] },
  { id: "vk", label: "VK", domains: ["vk.com", "vk.ru"] },
  {
    id: "stackOverflow",
    label: "Stack Overflow",
    domains: ["stackoverflow.com", "stackexchange.com"],
  },
  { id: "leetcode", label: "LeetCode", domains: ["leetcode.com"] },
  { id: "codeforces", label: "Codeforces", domains: ["codeforces.com"] },
  { id: "figma", label: "Figma", domains: ["figma.com"] },
  { id: "behance", label: "Behance", domains: ["behance.net"] },
  { id: "dribbble", label: "Dribbble", domains: ["dribbble.com"] },
  { id: "notion", label: "Notion", domains: ["notion.so", "notion.site"] },
  { id: "npm", label: "npm", domains: ["npmjs.com"] },
  { id: "vimeo", label: "Vimeo", domains: ["vimeo.com"] },
  { id: "soundcloud", label: "SoundCloud", domains: ["soundcloud.com"] },
  { id: "spotify", label: "Spotify", domains: ["spotify.com"] },
  { id: "boosty", label: "Boosty", domains: ["boosty.to"] },
  { id: "patreon", label: "Patreon", domains: ["patreon.com"] },
  { id: "tiktok", label: "TikTok", domains: ["tiktok.com"] },
  { id: "hackerone", label: "HackerOne", domains: ["hackerone.com"] },
  { id: "kaggle", label: "Kaggle", domains: ["kaggle.com"] },
  { id: "huggingface", label: "Hugging Face", domains: ["huggingface.co", "hf.co"] },
  { id: "devpost", label: "Devpost", domains: ["devpost.com"] },
  { id: "dockerHub", label: "Docker Hub", domains: ["hub.docker.com", "docker.com"] },
  { id: "pypi", label: "PyPI", domains: ["pypi.org"] },
  { id: "cratesIo", label: "crates.io", domains: ["crates.io"] },
  { id: "goDev", label: "Go Packages", domains: ["pkg.go.dev", "golang.org", "go.dev"] },
  { id: "codepen", label: "CodePen", domains: ["codepen.io"] },
  { id: "devTo", label: "DEV", domains: ["dev.to"] },
  { id: "hashnode", label: "Hashnode", domains: ["hashnode.com", "hashnode.dev"] },
  { id: "habr", label: "Habr", domains: ["habr.com"] },
  { id: "stepik", label: "Stepik", domains: ["stepik.org"] },
  { id: "coursera", label: "Coursera", domains: ["coursera.org"] },
  { id: "artstation", label: "ArtStation", domains: ["artstation.com"] },
  { id: "itch", label: "itch.io", domains: ["itch.io"] },
  { id: "steam", label: "Steam", domains: ["steamcommunity.com", "steampowered.com"] },
  { id: "googleScholar", label: "Google Scholar", domains: ["scholar.google.com"] },
  { id: "orcid", label: "ORCID", domains: ["orcid.org"] },
  { id: "researchGate", label: "ResearchGate", domains: ["researchgate.net"] },
  { id: "substack", label: "Substack", domains: ["substack.com"] },
  { id: "goodreads", label: "Goodreads", domains: ["goodreads.com"] },
  { id: "lastfm", label: "Last.fm", domains: ["last.fm"] },
  { id: "pinterest", label: "Pinterest", domains: ["pinterest.com", "pin.it"] },
  { id: "whatsapp", label: "WhatsApp", domains: ["whatsapp.com", "wa.me"] },
  { id: "signal", label: "Signal", domains: ["signal.org", "signal.me"] },
  { id: "matrix", label: "Matrix", domains: ["matrix.org", "matrix.to"] },
  { id: "keybase", label: "Keybase", domains: ["keybase.io"] },
  { id: "codewars", label: "Codewars", domains: ["codewars.com"] },
  { id: "hackerrank", label: "HackerRank", domains: ["hackerrank.com"] },
  { id: "kickstarter", label: "Kickstarter", domains: ["kickstarter.com"] },
  { id: "ycombinator", label: "Hacker News", domains: ["news.ycombinator.com", "ycombinator.com"] },
  { id: "producthunt", label: "Product Hunt", domains: ["producthunt.com"] },
]

const BY_DOMAIN: ReadonlyMap<string, ServiceDefinition> = new Map(
  SERVICES.flatMap((service) => service.domains.map((domain) => [domain, service] as const)),
)

export function serviceForDomain(domain: string): ServiceDefinition | null {
  return BY_DOMAIN.get(domain) ?? null
}
