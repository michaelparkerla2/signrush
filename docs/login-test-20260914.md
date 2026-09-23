# Web login test — 2026-09-14

Result: **Google login and sign-out verified in Chrome**.

Registered web app **SignRush Web Pilot** in `signrush-login`, app ID `1:886992538485:web:b705d95f40d03a9f49e13c`. No Firebase Hosting was enabled. The project's authorized-domain list already included `localhost`; no new domain was needed. Spark remains the selected plan.

Built `web/index.html`, `styles.css`, `firebase-config.js` and `login.js`. The public Firebase browser configuration was read from the registered app's General settings. It is not a service-account credential. The page loads Firebase JS SDK 12.19.0 from Google's CDN and uses Google popup login with in-memory persistence. It requests basic profile/email identity only. It does not request camera access, transmit recordings, accept corpus consent, award points, or call the participant API.

## Observed checks

- Local preview assets returned HTTP 200 with expected HTML/JavaScript/CSS MIME types and `Cache-Control: no-store`.
- The login button became ready after the SDK loaded.
- The in-app browser opened a pending popup flow but did not expose the popup for control; no successful in-app login is claimed.
- Chrome displayed Google's account chooser and the basic-profile/email confirmation for the Firebase client.
- The UMI account `michael@umi.vision` completed login. The page showed **Google sign-in worked** and the account email.
- Firebase Authentication's Users table independently showed the Google user, with creation and sign-in dated September 14, 2026.
- Clicking Sign out restored the Continue with Google view and removed the account display.
- No passwords or ID/refresh tokens were read, printed, or written to disk. The non-secret test UID is recorded in ignored `local-data/pilot-login.json` for the later runtime allowlist.

## Run locally

```sh
python3 tools/serve_login.py
```

Open `http://localhost:8088/` in Chrome. The tiny Python server binds only to `127.0.0.1` and serves only `web/`, not the repository, database, or local-data directory. Credentials are held only in the current page's memory; refresh/closing clears that session. The server was left running for the user to view this test, with no cloud runtime deployed.

## Next boundary

This confirms Firebase client login only. The player API and database are still not deployed or connected to this page. Next connect verified login to the restricted API, create the participant account after login, show and record consent before participation, and apply the one-user pilot allowlist. The chosen runtime service identity must be tested for revocation-check permissions in the login project and isolation from held-out answers in the storage project. The media worker and game flow remain subsequent work.
