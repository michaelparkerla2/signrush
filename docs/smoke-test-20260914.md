# Cloud media smoke test — 2026-09-14

Run: `smoke-20260914-01`. Result: **passed for administrator storage and private preview**.

Only a synthetic three-second test pattern was used. It is not ASL and must never enter training or evaluation datasets. No existing FLEURS samples were uploaded or modified.

## Verified

- Source and silent playback MP4 uploaded to private cloud storage and read back with matching SHA-256 hashes.
- Source copied within cloud storage into a release with a matching whole-file hash.
- JSON-array manifest and a synthetic-data README uploaded with the release.
- Authenticated byte-range read returned HTTP 206 and the expected bytes.
- Anonymous playback-object read returned HTTP 401.
- Raw and export buckets reported enforced public access prevention and uniform bucket access.
- Private Cloud Shell browser preview loaded a 320×180, three-second video. After native playback, its DOM reported `currentTime=3`, `duration=3`, `ended=true`, `readyState=4`, and no media error.
- The temporary preview server was stopped; Cloud Shell returned to its prompt.
- Earlier local checks generated the manifest through the database and extracted seconds 0.5–2.5 with the supplied pipeline's FFmpeg settings: 30 FPS, height at most 720, no audio. The model/external extractor itself was not run.

## Cloud artifacts

Raw prefix: `gs://umi-signrush-raw/smoke-tests/smoke-20260914-01/raw/`

| Asset | Filename | Bytes | SHA-256 |
|---|---|---:|---|
| Source | `8c70f8dd-37cc-4ec5-80b5-5dc1e9e6ad0e.mp4` | 50878 | `566127d288830fa9ee2d003db4ab7efeff8c735b8e24cee014a831a433749083` |
| Playback | `5c6d3a1d-214e-43e0-a9a8-ca3d9723ae6a.mp4` | 50802 | `a43998c4948c1a433dea1c52096567e2c18307cf8859b6c7900b761c2891ed26` |

Source object generation: `1789407637189986`. Playback generation: `1789407637541158`.

Release prefix: `gs://umi-signrush-exports/smoke-tests/smoke-20260914-01/synthetic-release/`

- `media/8c70f8dd-37cc-4ec5-80b5-5dc1e9e6ad0e.mp4`
- `records.json`
- `README.txt`
- `storage-receipt.json`

The cloud receipt was written before browser playback, so its `browser_playback` field says `not yet observed`. The later browser observation is recorded above. Cloud media total approximately 153 KB, plus small metadata files. Temporary generated local media and bundle were removed after verification; scripts remain reproducible.

## Boundaries

This checks administrator storage access, export packaging, and playback through the account-restricted Cloud Shell preview. Participant authentication, signed upload/playback endpoints, and held-out denial tests with distinct service identities remain unimplemented or untested. This does not validate ASL accuracy, automatic consensus, real payouts, or production deployment. No billing upgrade or IAM changes were made during this test.
