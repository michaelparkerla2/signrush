# Firebase Google sign-in setup — 2026-09-14

- Existing project `signrush`: Firebase attachment stopped at the explicit Blaze-plan confirmation. It was not confirmed.
- Created `signrush-login`, display name **SignRush Login**, under parent organization `umi.vision`.
- Console project number shown during provider setup: `886992538485`.
- Verified plan: **Spark — No-cost ($0/month)**.
- Optional Google Analytics and Google Developer Program enrollment were disabled during creation.
- Initialized Firebase Authentication; configured Google provider with public-facing name **SignRush** and support email **michael@umi.vision**.
- Final console result: **Success: Google enabled**; providers table shows **Google — Enabled**.
- New-project configuration initially returned transient access and save errors; a fresh console load and one save retry succeeded. No IAM role changes were made. A read-only Cloud Shell IAM command was attempted but no execution/output was observed, so it is not verification evidence.
- Existing video buckets remain in project `signrush`. No billing upgrade was confirmed and no video data was moved.

Console: https://console.firebase.google.com/project/signrush-login/authentication/providers

Backend configuration now expects Firebase project `signrush-login`. This is provider configuration only: no web app registration, actual player sign-in, invited UID, deployed API, or cross-project service-identity permission test has yet been completed. The future backend identity needs authentication-user read access in `signrush-login` for revocation checks; it must not receive broad access to held-out storage in `signrush`.

Firebase may allow a person to create an authentication identity once a web client is connected. The participant API's verified-email and explicit UID allowlist are what restrict pilot participation. Provider enablement alone is not an invitation gate.
