# Model Setup (Ollama and Gemini)

## How to Use Free Models Instead of Claude

### Default Setup (FREE - Recommended for now)

By default, the system now uses **Ollama** with **Mistral** model (completely free, runs locally).

**Steps to setup:**

1. **Install Ollama**
   ```bash
   # On Mac:
   brew install ollama
   
   # On Linux:
   curl https://ollama.ai/install.sh | sh
   
   # Or download from https://ollama.ai
   ```

2. **Pull a model**
   ```bash
   ollama pull mistral      # ~4GB, good quality/speed balance
   # or
   ollama pull neural-chat  # ~4GB, optimized for chat
   # or
   ollama pull llama2       # ~4GB, Meta's Llama 2
   ```

3. **Start Ollama server** (runs in background)
   ```bash
   ollama serve
   ```
   It will listen on `http://localhost:11434`

4. **Your app is ready!**
   - No API key needed
   - No cost
   - Runs completely locally
   - Works offline

### Using Claude Instead (PAID)

If you want to use Claude (high quality but costs money):

1. **Set environment variables in .env**
   ```env
   LLM_PROVIDER=claude
   CLAUDE_API_KEY=sk-...
   CLAUDE_MODEL=claude-opus-4-1
   ```

2. **That's it!** The system will automatically use Claude

### Using Gemini's Free Tier (Hosted)

Gemini runs remotely, so inference does not use your computer's memory or CPU.
Google's free tier has usage limits and may change. Prompts and portfolio context
are sent to Google, and free-tier content may be used to improve Google's
products. Avoid sending real financial data unless you accept those terms.

1. Create an API key in [Google AI Studio](https://aistudio.google.com/api-keys).
2. Add these settings to `.env` (do not commit the key):
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_api_key
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
3. Confirm the selected model is available on the free tier for your account,
   then restart the app.

Do not enable paid billing if you require a hard zero-cost limit. Free-tier
availability, model access, and quotas are controlled by Google and can change.

### Switching Back to Ollama

Just set in `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

Or remove those lines and restart (defaults to Ollama).

---

## Environment Variables

### Ollama (Default/Free)
```env
LLM_PROVIDER=ollama
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### Claude (Paid)
```env
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-...
CLAUDE_MODEL=claude-opus-4-1
```

### Gemini (Hosted Free Tier)
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

---

## Architecture

The LLM layer now uses a **provider abstraction**:

```
app/llm/
├── providers.py      # Abstract LLMProvider + implementations
│   ├── ClaudeProvider (paid)
│   ├── GeminiProvider (hosted)
│   └── OllamaProvider (local)
├── client.py         # LLMClient (uses any provider)
├── prompts.py        # System prompts (same for all)
└── context_builder.py # Context formatting (same for all)
```

**Adding a new provider is easy:**
1. Create a new class inheriting from `LLMProvider`
2. Implement `async analyze()` method
3. Add to `LLMFactory.create_provider()`
4. Set `LLM_PROVIDER=your_provider` in config

---

## Files Changed

- `app/llm/providers.py` (NEW) - Provider implementations
- `app/llm/client.py` - Refactored to use providers
- `app/llm/__init__.py` - Updated exports
- `app/config.py` - Added Ollama config
- `app/routes.py` - Updated initialization logic

---

## Quick Start

```bash
# 1. Install Ollama
brew install ollama

# 2. Start Ollama server (in another terminal)
ollama serve

# 3. Pull model
ollama pull mistral

# 4. Run your app
python run.py

# 5. Test chat endpoint
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my portfolio value?"}'
```

That's it! No API keys, no costs, completely local.

---

## Model Recommendations

| Model | Size | Speed | Quality | Download |
|-------|------|-------|---------|----------|
| **mistral** | 4GB | Fast | Good | `ollama pull mistral` |
| neural-chat | 4GB | Fast | Good | `ollama pull neural-chat` |
| llama2 | 4GB | Medium | Very Good | `ollama pull llama2` |
| llama2-uncensored | 4GB | Medium | Very Good | `ollama pull llama2-uncensored` |
| openhermes-2.5 | 4GB | Fast | Good | `ollama pull openhermes-2.5` |

**My recommendation:** Start with **mistral** - good balance of speed and quality.
