export const DOCS_BASE_URL =
  process.env.NEXT_PUBLIC_DOCS_BASE_URL ?? "https://github.com/taogroves/inky-easel/blob/main/docs";

export const DOC_LINKS = {
  overview: `${DOCS_BASE_URL}/README.md`,
  setup: `${DOCS_BASE_URL}/setup.md`,
  schedules: `${DOCS_BASE_URL}/schedules.md`,
  wifi: `${DOCS_BASE_URL}/wifi.md`,
  errors: `${DOCS_BASE_URL}/errors-and-troubleshooting.md`,
  developers: `${DOCS_BASE_URL}/for-developers.md`,
} as const;

export type DocLinkKey = keyof typeof DOC_LINKS;

export const DOC_CATALOG: Array<{ key: DocLinkKey; title: string; description: string }> = [
  {
    key: "overview",
    title: "Documentation overview",
    description: "Index of all guides and quick reference tables.",
  },
  {
    key: "setup",
    title: "Frame setup",
    description: "First-time SD card setup, flash loader, and verify connection.",
  },
  {
    key: "wifi",
    title: "Wi-Fi configuration",
    description: "Configure, SD setup, and on-frame network selection.",
  },
  {
    key: "schedules",
    title: "Schedule management",
    description: "Relative loops, calendar mode, and content types.",
  },
  {
    key: "errors",
    title: "Errors and troubleshooting",
    description: "On-frame messages, portal status, and fix checklists.",
  },
  {
    key: "developers",
    title: "For developers",
    description: "Developer mode, architecture, and design decisions.",
  },
];
