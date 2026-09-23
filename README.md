# SignRush

UMI’s mobile-first ASL game and private corpus project. Live pilot: **https://signrush-login.web.app/**.

**Start here: [Developer handoff and operations](docs/DEVELOPER_HANDOFF.md).** Developer permissions and first-use steps are in the [access register](docs/COLLABORATOR_ACCESS.md). This is the current source of truth; dated setup notes record earlier milestones and can describe states that have since changed.

## Live implementation

- Plain HTML/CSS/JavaScript in `web/`, hosted on Firebase Hosting.
- Google sign-in and Firestore in **`signrush-login`**. Verified Google users can register without invites; consent remains required.
- Python Cloud Shell worker in `tools/` for assignment, private upload, silent playback, independent reviews, exact-match pilot consensus, test points and queue summaries.
- Private Google Cloud Storage in **`signrush`**: `umi-signrush-raw`, `umi-signrush-heldout-answers`, `umi-signrush-exports`.
- Restricted Firestore rules keep player jobs private and prompts/peer answers out of validator responses. Server checks reject self-review, known same-person aliases and prompt exposure.

The worker is temporary (maximum **30 minutes** per run), not always-on. Recording reservations are capped at **three globally**, with **30-second / 8 MiB** clips. The pilot uses **test points with no cash value**. Cash payouts and the proposed unfunded $5,000 bonus are not active. The scorer is conservative normalized exact matching, not a calibrated 85% semantic/ASL accuracy model.

`backend/` and `db/` contain the locally tested FastAPI/PostgreSQL reference implementation and corpus schema/export functions. **They are not the deployed game backend.** Live Firestore submissions remain unqualified for training export; stable corpus signer mapping, split qualification and the production exporter still need implementation.

## Repository map

| Path | Contents |
|---|---|
| `web/` | Phone UI, recorder, onboarding, private Firestore job clients, rewards display |
| `tools/` | Live worker, scoring, dashboards, cloud smoke checks and administration helpers |
| `firestore/` | Deployed rules, emulator configuration and security tests |
| `data/pilot-phrases.json` | Three editable, UMI-authored pilot phrases |
| `backend/`, `db/migrations/` | Alternative/reference API and PostgreSQL corpus implementation |
| `tests/` | Browser controllers, pure logic, emulator transactions and reference DB/API tests |
| `docs/` | Current handoff, design and dated implementation evidence |
| `deliverables/` | Partner overview written before public registration opened |
| `AGENTS.md` | Rust/Cloudflare preferences and project constraints |

## Quick checks

```sh
node --test tests/*.mjs
python3 -m unittest discover -s tests -p 'test_signing_worker.py'
python3 -m unittest discover -s tests -p 'test_consensus.py'
python3 -m unittest discover -s tests -p 'test_dashboard.py'
```

For cloud setup, full emulator tests, deployment, data retrieval, collaborator access and recovery, use the [handoff](docs/DEVELOPER_HANDOFF.md).

## Collaboration and data

Keep this repository **private**. It contains source and operational documentation, not cloud credentials or participant media. Repository access does not grant Google Cloud/Firebase data access. Collaborators use their own identities and permissions on the two named projects. Keep large data in cloud storage; never commit videos, live database dumps, OAuth tokens, resumable upload URLs or signed playback links.

Prefer Rust for new backend services and Cloudflare Workers where suitable. No Cloudflare application is deployed and no Wrangler configuration exists yet. Migrate incrementally; preserve the working privacy, consent and transaction boundaries.
