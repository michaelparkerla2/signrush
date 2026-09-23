# Entry and responsive review — September 23, 2026

The landing CTA is now a button bound to the same Google popup handler as the sign-in card. Both buttons share loading/disabled state to prevent duplicate popups. Signup and returning sign-in use the same Google flow. Feedback appears beside the hero CTA as well as in the card. The requested early-access badge and card disclaimer were removed; reward accounting, cash availability and payment rules were not changed.

Footer on signed-out and signed-in screens: © 2026 UMI AI, Inc. All rights reserved. SignRush™ by UMI AI, Inc.

Browser viewport checks: landing 320×740, 390×844, 430×932, 768×1024, 820×1180, 1024×768, 1180×820 and 844×390; no horizontal overflow. Synthetic authenticated Home, Ranks, Sign and Decode layouts checked at widths 320, 390, 768, 820 and 1024; no overflow. Player and wallet dialogs fit the tablet viewport and remain scrollable. Added tablet columns, 44px account touch targets, 16px form text and safe-area/modal-height handling.

Clicking the CTA in the localhost preview reached the shared auth handler and displayed a recoverable Google network failure at both entry locations. This preview did not complete real Google authentication. Viewport checks do not certify real iOS Safari, virtual-keyboard, camera capture, network or every physical device. Existing camera behavior was not changed.

Live follow-up in regular Chrome: clicking Enter the Rush successfully opened Google Accounts' account chooser for the SignRush OAuth client. No account was selected and no user session was created. The embedded browser's Google network failure was not reproduced in Chrome.
