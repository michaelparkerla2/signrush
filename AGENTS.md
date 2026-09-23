# SignRush engineering preferences

- Prefer Rust for new backend services.
- Prefer Cloudflare Workers where suitable. Evaluate runtime limits for video processing; keep heavy media work in a suitable private worker service.
- Preserve existing Firebase/Google Cloud behavior during incremental migration. Do not rewrite working services merely to change languages.
- Keep corpus media and held-out references private, enforce server-side independent review, and preserve consent and test-only rewards.
- Use the existing free/trial scope; no paid upgrades are authorized.
