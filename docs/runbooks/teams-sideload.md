# Teams bot and tab sideload runbook

## External prerequisites

- A Teams/Microsoft 365 tenant that permits custom app upload.
- A public HTTPS deployment of the web/API stack.
- A real Teams application UUID.
- A single-tenant Azure Bot/Entra app registration with a client secret and test users.
- Configure the Bot messaging endpoint as
  `https://<public-host>/api/messages` and enable the Teams channel.
- For production tab identity: an Entra SPA/API registration, redirect URI, consent,
  and Nested App Authentication configuration.

## Build the package

```bash
TEAMS_APP_ID=00000000-0000-4000-8000-000000000000 \
APP_HOSTNAME=project-assistant.example.com \
make teams-package
```

The output is `dist/project-assistant-teams.zip`. The ZIP contains
`manifest.json`, `color.png`, and `outline.png` at its root.

The backend must use these settings (values are examples only):

```dotenv
APP_ENV=production
AUTH_MODE=entra
DEV_AUTH_ENABLED=false
TEAMS_TRANSPORT=sdk
TEAMS_APP_ID=00000000-0000-4000-8000-000000000000
TEAMS_APP_PASSWORD=<secret-manager-reference>
TEAMS_SKIP_AUTH=false
ENTRA_TENANT_ID=00000000-0000-4000-8000-000000000000
```

`TEAMS_SKIP_AUTH=true` is accepted only in `local`/`test`; staging and production
refuse to start with unauthenticated bot activities.

## Sideload

In Teams, open **Apps → Manage your apps → Upload an app → Upload a custom app**,
select the ZIP, then choose **Add**. The app exposes a personal tab plus a bot in
personal chat, group chat, and Team/channel scopes. Mention the bot followed by
`/help`, or use `/help` in personal chat, to discover commands allowed by the user's
Team role. Teams hosts neither the web application nor the bot endpoint.

Group and channel installations are unbound initially. A PM must bind the conversation
to one application Team before scoped actions can run; Tech Leads cannot change this
binding. Personal chat remains unbound so a member can select among all Teams where
they hold a membership.

The checked-in manifest is a template. The SDK adapter and package are locally tested,
but do not claim a real Teams/Entra/proactive-delivery integration until the external
gates are open and an installed-app smoke test has passed in the target tenant.
