# VST Gen Agent — Repository Instructions

This repository contains the `@vst-gen` VS Code Copilot agent and supporting tools for
generating VST3/AU/Standalone MIDI controller plugins from hardware synthesizer front panels.

## How This Repo Works

| Folder | Purpose |
|--------|---------|
| `.github/agents/` | VS Code Copilot custom agent definition (`vst-gen.agent.md`) |
| `.github/skills/` | Agent skill files (SKILL.md + supporting scripts) |
| `.github/prompts/` | Slash-command prompt files (`/new-device`, `/login`) |
| `.github/workflows/` | CI/CD + registry maintenance workflows |
| `api/` | FastAPI registry service deployed to Cloud Run |
| `terraform/` | GCP + GitHub infrastructure (WIF, Cloud Run, Scheduler, Actions secrets) |
| `tools/` | Python CLI tools (midi_capture.py, vision_coords.py, scaffold.py, registry_client.py, seed_registry.py) |
| `templates/juce/` | JUCE 8 plugin boilerplate templates (`.tmpl` files) |
| `templates/elementary/` | Elementary Audio plugin boilerplate templates |
| `devices/` | Generated device-specific plugin projects (git-ignored by default) |
| `docs/` | Auto-generated docs (device-index.md updated daily by workflow) |

## Quick Start

1. Open this repo in VS Code alongside your target device workspace.
2. Type `@vst-gen /new-device` in GitHub Copilot Chat.
3. Follow the guided workflow: provide device name, panel image, and manual.
4. The agent runs the MIDI capture → coordinate detection → scaffold pipeline.
5. Build with `make run` from the generated device folder.

## Adding a New Device Manually

```bash
# 1. Capture NRPN params from hardware
python3 tools/midi_capture.py --capture --device "MyDevice" --output my_nrpn_map.json

# 2. Detect knob positions in panel photo
python3 tools/vision_coords.py --image my_panel.png --scale 0.5 --output my_coords.json

# 3. Scaffold the plugin
python3 tools/scaffold.py \
  --framework juce \
  --map my_nrpn_map.json \
  --coords my_coords.json \
  --panel my_panel.png \
  --output devices/MyDevice/

# 4. Build and run
cd devices/MyDevice && make run

# 5. Share your capture
python3 tools/registry_client.py push my_nrpn_map.json --repo YourOrg/YourPluginRepo
```

## Device Registry

The shared community registry stores pre-captured device maps. All entries must be backed by
a **public GitHub repo** — this is enforced at submission and re-verified daily.

```bash
python3 tools/registry_client.py list               # browse active devices
python3 tools/registry_client.py pull <slug>        # download + optional git clone
python3 tools/registry_client.py login              # GitHub device flow → API key
python3 tools/registry_client.py push nrpn.json     # contribute (requires login)
```

### Authentication (GitHub device flow)

Registration is bound to a GitHub account — no email form or password:

```bash
# Set the OAuth App client ID once (get from the registry operator or README)
python3 tools/registry_client.py set-github-client-id <CLIENT_ID>

# Login — opens github.com/login/device with a short code
python3 tools/registry_client.py login
```

Scopes granted: `read:user user:email` (read-only). Key saved to `~/.vst-gen-token`.

### Device Staleness

Entries are re-validated daily by Cloud Scheduler. A device is marked `stale` if its
GitHub repo is deleted or made private after indexing. `GET /devices` filters stale
entries by default; `GET /devices/{slug}` returns HTTP 410 Gone for stale entries.

## Deploying the Registry

All infrastructure is managed by Terraform. **One-time setup:**

### Step 1 — Create the GitHub OAuth App (manual, one-time)

Terraform cannot create OAuth Apps. Do this in the GitHub UI before running `terraform apply`.

**Organization account:**
```
https://github.com/organizations/<org>/settings/applications → New OAuth App
```

**Personal account:**
```
https://github.com/settings/developers → New OAuth App
```

Fill in the form:

| Field | Value |
|-------|-------|
| Application name | `VST Gen Registry` |
| Homepage URL | Use `https://localhost` as a placeholder (update after first apply) |
| Authorization callback URL | `https://localhost` (device flow never redirects — field is unused) |

After registration:
1. Scroll to **"Enable Device Flow"** on the app settings page and check it — required for the CLI login flow
2. Copy the **Client ID** from the top of the page (not sensitive; safe to store as a Terraform variable)
3. Do **not** generate a client secret — the device flow for public clients does not need one

### Step 2 — Terraform apply

```bash
cd terraform

# Copy and configure GCS state backend
cp gcs.tfbackend.example gcs.tfbackend
# Set: bucket = "<your-state-bucket>", prefix = "vst-gen-registry"

# Apply — sets up Cloud Run, WIF, Scheduler, and all Actions secrets automatically
terraform init -backend-config=gcs.tfbackend
TF_VAR_github_token=<PAT with repo scope> \
TF_VAR_revalidation_api_key=vst_<key> \
TF_VAR_github_oauth_client_id=<client_id_from_step_1> \
terraform apply
```

After apply, all GitHub Actions secrets (`GCP_WORKLOAD_IDENTITY_PROVIDER`,
`GCP_SERVICE_ACCOUNT`, `REGISTRY_URL`, `REGISTRY_API_KEY`) and the
`GITHUB_OAUTH_CLIENT_ID` variable are set automatically — no manual copy-paste needed.

> **After first apply**: Update the OAuth App's Homepage URL in GitHub to the live
> Cloud Run URL output by Terraform (`terraform output registry_url`).

## Environment Requirements

- macOS 13+ (for VST3/AU/Standalone)
- Xcode Command Line Tools
- CMake 3.22+, Ninja (`brew install cmake ninja`)
- Python 3.11+ with: `pip install pillow numpy opencv-python-headless mido python-rtmidi`
- Node.js 20+ (for Elementary Audio templates only)

## macOS 15+ Note

On macOS 15 (Sequoia) and later, the CLT stub for C++ stdlib headers is missing.
The Makefile automatically sets `CPLUS_INCLUDE_PATH` to the SDK path. If you see
`#include <string>` errors, verify the SDK path in the Makefile matches your installed SDK:

```bash
ls /Library/Developer/CommandLineTools/SDKs/
```

