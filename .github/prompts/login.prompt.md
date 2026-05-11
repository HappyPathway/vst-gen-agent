---
name: login
description: "Register with the VST Gen community device registry using your GitHub account, or configure an existing API key. Use when: setting up the registry for the first time; entering an API key the user already has; switching registry accounts."
argument-hint: "New user (GitHub login) or existing API key"
---

# Login — VST Gen Device Registry

One-time setup to connect the `@vst-gen` agent to the shared device registry.
Authentication is bound to your **GitHub account** — no separate password needed.

## Step 1 — Prerequisites

The login command requires a GitHub OAuth App `client_id` to be configured once:

```bash
python3 tools/registry_client.py set-github-client-id <CLIENT_ID>
```

If the registry operator hasn't shared a `CLIENT_ID` with you, ask them or check the
[vst-gen-agent repo](https://github.com/HappyPathway/vst-gen-agent) README.
You can also set it via env var: `export VST_GEN_GITHUB_CLIENT_ID=<CLIENT_ID>`.

## Step 2 — Authenticate via GitHub

```bash
python3 tools/registry_client.py login
```

This runs the **GitHub device flow**:
1. A URL and short code are printed in the terminal
2. Open the URL in your browser and enter the code
3. Authorize the `vst-gen-registry` OAuth App (scopes: `read:user user:email` — read-only)
4. The CLI polls GitHub until you authorize, then registers your GitHub identity with the registry
5. Your `vst_...` API key is saved to `~/.vst-gen-token` (chmod 600)

Your API key is returned **once** — it's immediately saved locally.

## Step 3 — Verify

```bash
python3 tools/registry_client.py whoami
```

Should show your GitHub username and any devices you've contributed.

## Step 4 — Configure registry URL (first time only)

After Terraform deploy, get the URL:
```bash
cd terraform && terraform output registry_url
```

Then:
```bash
python3 tools/registry_client.py set-url https://vst-gen-registry-<hash>-uc.a.run.app
```

Or set it for all tools in one shell:
```bash
export VST_GEN_REGISTRY_URL=https://vst-gen-registry-<hash>-uc.a.run.app
```

## Using an existing key

If you already have a key (e.g. from another machine):
```bash
echo "vst_<your-key>" > ~/.vst-gen-token
chmod 600 ~/.vst-gen-token
```

## Security notes

- Your API key is stored in `~/.vst-gen-token` (chmod 600 — readable only by you)
- The key is sent only to the registry endpoint via HTTPS
- Device maps are public; your email is never exposed in API responses
