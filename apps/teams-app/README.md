# Teams app package

The Teams app is a personal static tab that embeds the same React SPA as the standalone
web application. Teams hosts only the manifest and icons; deploy the web/API stack to a
public HTTPS hostname first.

Build a sideloadable package:

```bash
TEAMS_APP_ID=00000000-0000-4000-8000-000000000000 \
APP_HOSTNAME=project-assistant.example.com \
make teams-package
```

The ZIP is written to `apps/teams-app/build/project-assistant-teams.zip`. Upload it from
Teams **Apps → Manage your apps → Upload a custom app**. The tenant must permit custom
app upload.

`TEAMS_APP_ID` must be a real UUID and `APP_HOSTNAME` must be a public hostname without
a scheme or path. Entra/NAA and the bot are intentionally not declared until their
registrations and hosted endpoints exist; the current package is the tab capability.
