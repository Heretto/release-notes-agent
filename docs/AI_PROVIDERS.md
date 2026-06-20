# Configuring AI Providers

The Release Notes Agent supports three AI providers: **Anthropic Claude**, **OpenAI GPT**, and **Google Gemini**. You can configure providers through the application UI or via environment variables.

---

## Overview

| Provider | Recommended Model | API Key Prefix | Env Var |
|---|---|---|---|
| Anthropic Claude | `claude-3-5-sonnet-20241022` | `sk-ant-` | `ANTHROPIC_API_KEY` |
| OpenAI GPT | `gpt-4o` | `sk-` | — (UI only) |
| Google Gemini | `gemini-2.5-pro` | — | `GOOGLE_AI_API_KEY` |

At least one provider must be configured. When a job does not specify a provider, the system falls back in this order: Gemini → Anthropic → OpenAI.

---

## Configuring via the UI

All three providers can be configured through **Settings > AI Credentials**.

1. Open the application and navigate to **Settings > AI Credentials**.
2. Click **Add Credential**.
3. Select the provider from the dropdown.
4. Enter a name for the credential (used to identify it in job configuration).
5. Paste your API key.
6. Optionally specify a model name to override the default.
7. Click **Test Connection** to verify the credential before saving.
8. Click **Save**.

You can store multiple credentials per provider (e.g., different keys for different teams or projects). When creating a job, select the credential to use; if none is selected the system uses the fallback order above.

---

## Anthropic Claude

### Getting an API key

1. Sign in or create an account at [console.anthropic.com](https://console.anthropic.com).
2. Navigate to **API Keys** and click **Create Key**.
3. Copy the key — it will not be shown again.

Anthropic API keys begin with `sk-ant-`.

### Environment variable configuration

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Setting this variable pre-loads a system-level Anthropic credential. It can still be overridden per-job by a credential configured in the UI.

### Supported models

Any model available in your Anthropic account can be used. Common options:

| Model | Notes |
|---|---|
| `claude-3-5-sonnet-20241022` | Default. Strong balance of speed and quality. |
| `claude-sonnet-4-20250514` | Latest Sonnet generation. |
| `claude-opus-4-8` | Highest capability, slower and more expensive. |
| `claude-haiku-4-5-20251001` | Fastest, lowest cost. |

### Notes

- The API key is validated at save time by sending a test request to `https://api.anthropic.com/v1/messages`.
- Token usage (input and output) is tracked and returned with each generation.

---

## OpenAI GPT

### Getting an API key

1. Sign in or create an account at [platform.openai.com](https://platform.openai.com).
2. Navigate to **API Keys** and click **Create new secret key**.
3. Copy the key — it will not be shown again.

OpenAI API keys begin with `sk-`.

### Environment variable configuration

OpenAI credentials are configured per-user through the UI only. There is no environment variable fallback for OpenAI.

### Supported models

Any chat completion model in your OpenAI account can be used. Common options:

| Model | Notes |
|---|---|
| `gpt-4o` | Recommended. Multimodal, fast, cost-efficient. |
| `gpt-4-turbo-preview` | Default in the adapter. |
| `gpt-4` | Strong reasoning, higher cost. |
| `gpt-3.5-turbo` | Fast and low cost; lower output quality. |
| `o1`, `o1-mini` | Extended reasoning models. |

The adapter automatically handles the `max_tokens` vs `max_completion_tokens` parameter difference between older and newer OpenAI models.

### Notes

- The API key is validated at save time by sending a test request to `https://api.openai.com/v1/chat/completions`.
- Token usage (prompt, completion, and total) is tracked and returned with each generation.

---

## Google Gemini

### Getting an API key

1. Sign in at [aistudio.google.com](https://aistudio.google.com).
2. Click **Get API key** and then **Create API key**.
3. Copy the key.

### Environment variable configuration

```env
GOOGLE_AI_API_KEY=your-api-key-here
GOOGLE_AI_MODEL=gemini-2.5-pro
```

`GOOGLE_AI_MODEL` is optional; if omitted the adapter defaults to `gemini-2.5-pro`.

### Supported models

Any model available in your Google AI Studio account can be used. Common options:

| Model | Notes |
|---|---|
| `gemini-2.5-pro` | Default. Most capable Gemini model. |
| `gemini-2.5-flash` | Faster and cheaper than Pro. |
| `gemini-1.5-pro` | Previous generation Pro. |
| `gemini-1.5-flash` | Previous generation Flash. |

You can pass the model name with or without the `models/` prefix — the adapter strips it automatically.

### Notes

- The API key is validated at save time by sending a test request to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
- Gemini does not return per-request token counts in the same way as Anthropic and OpenAI; token usage fields will be `0` in the job response.

---

## Troubleshooting

### "API key has unexpected prefix"

This is a warning, not an error. Anthropic and OpenAI keys are expected to start with `sk-` or `sk-ant-` respectively. If you see this in logs but the connection test passes, the key is still valid.

### Connection test fails for Gemini

- Ensure the **Generative Language API** is enabled in your Google Cloud project.
- Check that the model name is spelled correctly and available in your account (e.g., `gemini-2.5-pro`, not `gemini-pro-2.5`).

### Connection test fails for Anthropic

- Confirm the key starts with `sk-ant-` and has not been revoked in the Anthropic console.
- Check that your Anthropic account has credits or an active billing plan.

### Connection test fails for OpenAI

- Confirm the key starts with `sk-` and is not expired.
- For `o1` / `o1-mini` models, ensure your account has access — these models require additional enrollment.

### Job uses the wrong provider

If a job runs with a different provider than expected, check:
1. Whether an explicit **AI Credential** is selected in the job configuration.
2. The fallback order (Gemini → Anthropic → OpenAI) — the first credential found in that order will be used when none is specified.
