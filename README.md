# VST Gen Agent

<!-- registry-stats -->
![Devices indexed](https://img.shields.io/badge/devices_indexed-0-blue)  ![Contributors](https://img.shields.io/badge/contributors-0-green)
<!-- /registry-stats -->
![License](https://img.shields.io/github/license/HappyPathway/vst-gen-agent)
![Last commit](https://img.shields.io/github/last-commit/HappyPathway/vst-gen-agent)

VS Code Copilot agent that generates complete **VST3 / AU / Standalone** MIDI controller
plugins from hardware synthesizer front panels.  
Captures NRPN/CC parameters directly from hardware, detects knob positions in a panel
photo, scaffolds a buildable JUCE 8 project, and registers the device in a shared
community registry — all from a single chat prompt.

---

## Quick Start (VS Code)

```
@vst-gen /new-device
```

The agent walks you through:
1. Checking the community registry — device might already be captured
2. Extracting parameters from the device manual (PDF or URL)
3. Running an interactive NRPN/CC capture session against live hardware
4. Detecting knob positions in a front-panel photo
5. Scaffolding a complete JUCE 8 plugin project
6. Building and running the plugin locally
7. Publishing the captured map back to the community registry

---

## Community Device Registry

A shared backend indexes NRPN/CC maps for hardware devices.
All entries are backed by **public GitHub repos** — no private hosting required.

```bash
# Browse
python3 tools/registry_client.py list

# Pull a device someone else already captured
python3 tools/registry_client.py pull sequential-take5

# Register your GitHub account (one-time, device flow — no password)
python3 tools/registry_client.py login

# Publish your capture
python3 tools/registry_client.py push nrpn_map.json \
  --slug sequential-take5 \
  --repo HappyPathway/Take5-VST
```

Registry badges update daily from `GET /stats`. Stale entries (deleted or privatised repos)
are detected daily by Cloud Scheduler and marked accordingly.

---

## Adding a Device Manually

```bash
# 1. Capture NRPN params from hardware
python3 tools/midi_capture.py --capture --device "MyDevice" --output nrpn_map.json

# 2. Detect knob positions in panel photo
python3 tools/vision_coords.py --image panel.png --scale 0.5 --output coords.json

# 3. Scaffold the plugin
python3 tools/scaffold.py \
  --framework juce \
  --map nrpn_map.json \
  --coords coords.json \
  --panel panel.png \
  --output devices/MyDevice/

# 4. Build and run
cd devices/MyDevice && make run

# 5. Push plugin code to a public GitHub repo, then share the capture
python3 tools/registry_client.py push nrpn_map.json \
  --repo YourOrg/YourPluginRepo
```

---

## What Gets Generated

```
devices/<DeviceName>/
  panel.png                  ← front-panel backdrop image
  nrpn_map.json              ← captured MIDI parameter map
  src/
    PluginProcessor.cpp/h    ← JUCE NRPN send/receive + APVTS
    PluginEditor.cpp/h       ← panel UI with knobs overlaid on image
    DeviceParameters.h       ← parameter layout + NRPN address table
    midi/
      NrpnSender.cpp/h       ← 14-bit NRPN encoding over MIDI
      UsbMidiManager.cpp/h   ← USB auto-reconnect with polling
  CMakeLists.txt
  Makefile                   ← `make run` builds + launches Standalone
  README.md
```

---

## Reference Implementation

[**HappyPathway/Take5-VST**](https://github.com/HappyPathway/Take5-VST) — Sequential Take 5  
42 NRPN params · brushed-aluminum LookAndFeel · panel.png backdrop · macOS 13+

---

## Supported Frameworks

| Framework | Output | Use When |
|-----------|--------|----------|
| **JUCE 8** | VST3 + AU + Standalone | Professional DAW plugin (default) |
| **Elementary Audio** | WebAudio / Node | Rapid prototyping, web-first |

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `.github/agents/vst-gen.agent.md` | VS Code Copilot custom agent definition |
| `.github/skills/` | Agent skill files (SKILL.md + supporting scripts) |
| `.github/prompts/` | Slash-command prompts (`/new-device`, `/login`) |
| `.github/workflows/` | CI/CD and registry maintenance (see below) |
| `api/` | FastAPI registry service (Cloud Run) |
| `terraform/` | GCP + GitHub infrastructure as code |
| `tools/` | Python CLI tools |
| `templates/juce/` | JUCE 8 plugin boilerplate (`.tmpl` files) |
| `templates/elementary/` | Elementary Audio boilerplate |
| `devices/` | Generated device projects (git-ignored) |
| `docs/device-index.md` | Auto-generated device index (updated daily) |

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/midi_capture.py` | Interactive NRPN/CC capture from live hardware |
| `tools/vision_coords.py` | Detect knob positions in front-panel photos |
| `tools/scaffold.py` | Generate plugin project from map + coords + templates |
| `tools/registry_client.py` | Registry CLI: login, list, push, pull |
| `tools/seed_registry.py` | Bulk-upload from `iron-static` device database |

### `registry_client.py` subcommands

| Command | Description |
|---------|-------------|
| `login` | GitHub device flow → register identity → save API key |
| `whoami` | Show your GitHub login and contributed devices |
| `list` | List all active devices in the registry |
| `get <slug>` | Fetch a device map |
| `push <map.json>` | Submit or update a device map |
| `pull <slug>` | Download a map and optionally clone the plugin repo |
| `set-url <url>` | Configure the registry base URL |
| `set-github-client-id <id>` | Store the GitHub OAuth App client ID |

---

## Agent Skills

| Skill | Trigger |
|-------|---------|
| `midi-capture` | Capture NRPN/CC parameters from live hardware |
| `extract-params` | Parse parameters from a device manual (PDF or URL) |
| `vision-to-coords` | Map a panel photo to pixel coordinates for each knob |
| `scaffold-vst` | Generate a complete JUCE 8 plugin project |
| `share-device` | Pre-flight git checks + push to community registry |

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy-registry.yml` | Push to `api/` or `terraform/` | Build Docker image → push to Artifact Registry → deploy to Cloud Run |
| `registry-health.yml` | PR to `api/` + push to master | Smoke-test the live API: health, schema, 404 behaviour |
| `revalidate.yml` | Daily 03:15 UTC + manual | Call `POST /admin/revalidate`; mark stale / restore active entries |
| `update-device-index.yml` | Daily 03:30 UTC + push to `api/` | Regenerate `docs/device-index.md` from live registry |
| `update-readme-stats.yml` | Daily 03:45 UTC + manual | Patch README badge counts from `GET /stats` |

All secrets (`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `REGISTRY_URL`,
`REGISTRY_API_KEY`) and the `GITHUB_OAUTH_CLIENT_ID` variable are managed by Terraform —
no manual copy-paste into GitHub settings required.

---

## Infrastructure (Terraform)

All GCP and GitHub infrastructure is defined in `terraform/`:

```
terraform/
  main.tf       ← providers, APIs, Artifact Registry, Cloud Run, Cloud Scheduler
  wif.tf        ← Workload Identity Federation (keyless GitHub Actions → GCP)
  github.tf     ← GitHub Actions secrets + GITHUB_OAUTH_CLIENT_ID variable
  variables.tf  ← all input variables with descriptions
  outputs.tf    ← registry_url, docker_image_repo, WIF provider, deploy SA
```

### First-time deploy

```bash
cd terraform

# 1. Copy and fill in the GCS state backend config
cp gcs.tfbackend.example gcs.tfbackend
# Set: bucket = "<your-state-bucket>", prefix = "vst-gen-registry"

# 2. Create a GitHub OAuth App manually (Terraform cannot do this):
#    https://github.com/organizations/HappyPathway/settings/applications
#    Name: VST Gen Registry | Homepage: <your registry URL> | No callback URL
#    Copy the Client ID (not sensitive)

# 3. Register a revalidation API key:
#    python3 tools/registry_client.py login   (after first deploy)
#    Copy the vst_... key

# 4. Apply
terraform init -backend-config=gcs.tfbackend
TF_VAR_github_token=<PAT with repo scope> \
TF_VAR_revalidation_api_key=vst_<key> \
TF_VAR_github_oauth_client_id=<client_id> \
terraform apply
```

After `apply`, all GitHub Actions secrets are set automatically. Redeploy the
Cloud Run image via the `deploy-registry.yml` workflow or:

```bash
docker build -t \
  us-central1-docker.pkg.dev/happypathway-1522441039906/vst-gen/registry-api:latest \
  ./api
docker push \
  us-central1-docker.pkg.dev/happypathway-1522441039906/vst-gen/registry-api:latest
```

---

## Registry API

The live registry exposes a minimal REST API:

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /` | — | Health check + version |
| `GET /stats` | — | Device + contributor counts |
| `GET /devices` | — | List active devices (`?include_stale=true` for stale) |
| `GET /devices/{slug}` | — | Fetch a device (410 if stale) |
| `POST /auth/register-github` | GitHub OAuth token | Register GitHub identity → API key |
| `GET /auth/me` | X-API-Key | Profile + contributed device list |
| `POST /devices` | X-API-Key | Submit a device map |
| `PUT /devices/{slug}` | X-API-Key + ownership | Update a device map |
| `DELETE /devices/{slug}` | X-API-Key + ownership | Remove a device map |
| `POST /admin/revalidate` | X-API-Key | Re-check all indexed repos for staleness |

API docs (Swagger UI): `<registry_url>/docs`  
ReDoc: `<registry_url>/redoc`

---

## Authentication

Registration uses the **GitHub device flow** — no password, no email form:

```bash
python3 tools/registry_client.py set-github-client-id <OAUTH_APP_CLIENT_ID>
python3 tools/registry_client.py login
# → Opens github.com/login/device with a short code
# → Grants read:user + user:email scopes only
# → Saves vst_... key to ~/.vst-gen-token (chmod 600)
```

Identity is bound to your GitHub account. The API key is issued once — store it safely.

---

## Requirements

- **macOS 13+** — VST3 / AU / Standalone build target
- **Xcode Command Line Tools** — `xcode-select --install`
- **CMake 3.22+** and **Ninja** — `brew install cmake ninja`
- **Python 3.11+** — `pip install pillow numpy opencv-python-headless mido python-rtmidi`
- **Node.js 20+** — Elementary Audio templates only

### macOS 15+ note

The CLT stub for C++ stdlib headers is missing on macOS 15 (Sequoia).
The generated Makefile sets `CPLUS_INCLUDE_PATH` automatically. If you see
`#include <string>` errors, verify the SDK path:

```bash
ls /Library/Developer/CommandLineTools/SDKs/
```

---

Part of the [HappyPathway](https://github.com/HappyPathway) open-source toolchain.

