---
name: login
description: "Register with the VST Gen community device registry or configure an existing API key. Use when: setting up the registry for the first time; entering an API key the user already has; switching registry accounts."
argument-hint: "Email address or existing API key"
---

# Login — VST Gen Device Registry

One-time setup to connect the `@vst-gen` agent to the shared device registry.

## Step 1 — Choose your path

**New user:** Register an email to receive an API key
**Existing key:** Enter a key you already have

## Step 2 — Register (new users)

```bash
python3 tools/registry_client.py login
```

You'll be prompted for email and optional display name. Your API key is returned **once** — it's immediately saved to `~/.vst-gen-token`.

## Step 3 — Verify

```bash
python3 tools/registry_client.py whoami
```

Should show your email and any devices you've contributed.

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
