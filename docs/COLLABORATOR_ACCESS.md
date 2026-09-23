# Developer access register

Configured 2026-09-23 at the owner’s request. This register documents SignRush access, not access to other UMI projects.

| Developer | GitHub | Google identity |
|---|---|---|
| Sam | `sam0x17` | `sam@umi.vision` |
| maintainer | `authorized-collaborator` | `contributor@users.noreply.github.com` |

## GitHub

Repository: https://github.com/michaelparkerla2/signrush — private.

Both users were invited with **Write** permission. This permits cloning the complete repository, pushing changes, branches, pull requests and collaboration. Invitations must be accepted using the named GitHub accounts. GitHub rejected `admin` permission for these collaborators on the personally owned repository; owner-level settings are still controlled by `michaelparkerla2`. An organization transfer would be a separate change if shared repository administration is desired.

## Google Cloud / Firebase

All 16 direct role bindings (eight per person) were read back and verified on 2026-09-23. The three bucket policies contain no allUsers/allAuthenticatedUsers principals, and the existing playback-prefix condition remains present. This verifies configured IAM, not either collaborator’s personal sign-in session.

For **each** named Google identity:

| Scope | Role | Purpose |
|---|---|---|
| Project `signrush-login` | `roles/firebase.admin` | Manage Firebase application services, Hosting, Auth, Firestore data and security rules |
| Project `signrush-login` | `roles/serviceusage.serviceUsageConsumer` | Use enabled project APIs/quota with their own credentials |
| Project `signrush` | `roles/viewer` | Inspect the media project and existing resource configuration |
| Project `signrush` | `roles/serviceusage.serviceUsageConsumer` | Use enabled media-project APIs |
| Bucket `umi-signrush-raw` | `roles/storage.admin` | Manage original/failed videos, playback derivatives and review evidence |
| Bucket `umi-signrush-heldout-answers` | `roles/storage.admin` | Manage private prompts/references for authorized development/research |
| Bucket `umi-signrush-exports` | `roles/storage.admin` | Manage versioned private research/export objects |
| Service account `signrush-playback@signrush.iam.gserviceaccount.com` | `roles/iam.serviceAccountTokenCreator` | Run the existing keyless private playback-signing flow |

These are substantial administrative data permissions, including editing/deleting data within their granted scope. They are not billing-account ownership, organization administration, or unrestricted project IAM administration. Use individual credentials; no owner passwords, downloaded service-account keys or OAuth tokens are shared.

The playback service account itself retains its separate prefix-limited read policy; developer access does not require making media or reference answers public. Human corpus maintainers can inspect held-out answers. Training runtime identities must still be restricted to qualified release paths to preserve evaluation isolation.

## First use

1. Accept the GitHub collaboration invitation and clone the private repo.
2. Sign into Firebase/Google Cloud as the listed `@umi.vision` account; allow for IAM propagation.
3. Read `docs/DEVELOPER_HANDOFF.md` before running a worker, changing rules or exporting data.
4. Use a separate Cloud Shell home/checkout. Coordinate a single live worker operator.
5. Confirm their own login/deploy/read operations before relying on access for an urgent task; the owner can verify IAM bindings but cannot prove another person’s session works.

No Cloudflare membership has been granted: no Cloudflare application/account migration is configured yet. The Rust/Cloudflare preference is recorded in `AGENTS.md`.
