# Teams tab sideload runbook

## External prerequisites

- A Teams/Microsoft 365 tenant that permits custom app upload.
- A public HTTPS deployment of the web/API stack.
- A real Teams application UUID.
- For production identity: an Entra SPA/API registration, redirect URI, consent, and
  test users. Entra NAA is not enabled in the tab-only package yet.

## Build the package

```bash
TEAMS_APP_ID=00000000-0000-4000-8000-000000000000 \
APP_HOSTNAME=project-assistant.example.com \
make teams-package
```

The output is `apps/teams-app/build/project-assistant-teams.zip`. The ZIP contains
`manifest.json`, `color.png`, and `outline.png` at its root.

## Sideload

In Teams, open **Apps → Manage your apps → Upload an app → Upload a custom app**,
select the ZIP, then choose **Add** and **Open**. Teams loads the hosted SPA in a
personal tab; it does not host the web application itself.

The checked-in manifest is a template. Do not claim real Teams, Entra, bot, or
proactive-message integration until the external gates are open and an installed-app
smoke test has passed in the target tenant.
