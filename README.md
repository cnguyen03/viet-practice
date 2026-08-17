# viet-practice

A Vietnamese speaking-practice partner that runs entirely on your laptop. The
LLM, the speech recognition, and the voice are all local, so a session needs no
internet and no cell signal — the laptop broadcasts its own Wi-Fi network and
your phone joins it directly. Built for practising on a bus or in a car.

You speak Vietnamese into your phone; the agent replies out loud, keeps the
conversation on one topic, and when you get stuck it teaches you a phrase and
waits for you to say it back.

Conversations are grounded in a local vocabulary file you control
(`data/vietnamese_progress.json`), so the agent talks at your level and
deliberately reinforces the words you find shaky.

---

## What you need

- **A Mac** (Apple Silicon recommended — developed on an M3 Pro, 18 GB RAM).
  macOS is required: the Vietnamese voice `Linh` ships with the OS, and the
  offline hotspot uses macOS Internet Sharing.
- **A phone** with a modern browser. No app to install.
- **~6 GB of disk** for the language and speech models.
- **Internet for setup only.** Once set up, nothing needs a network again.

---

## Part 1 — Server setup (laptop)

Do this once, at home, with internet.

### 1. Install the tooling

```bash
brew install ollama uv
brew services start ollama
```

### 2. Pull the language model (~4.7 GB)

```bash
ollama pull qwen2.5:7b-instruct
```

### 3. Install Python dependencies

```bash
cd viet-practice
uv sync
```

### 4. Generate the TLS certificate

```bash
./scripts/make_cert.sh
```

**This step is not optional.** Browsers only allow microphone access on a
"secure context". `http://localhost` qualifies, but the LAN address your phone
uses (`https://192.168.2.1:8000`) does not — over plain HTTP the phone's mic is
silently blocked. The certificate is what makes speaking possible.

### 5. Add your vocabulary

The agent can only talk about words it knows you know. The shipped file is a
small placeholder — replace it with your own:

```bash
cat <<'JSON' | uv run scripts/vocab.py add
[
  {"vi": "chợ", "en": "market", "strength": 0.4},
  {"vi": "cà phê", "en": "coffee", "strength": 0.8}
]
JSON

uv run scripts/vocab.py show
```

In Claude Code, the `/update-vocab` skill does this for you — paste the words
you've learned or say which Duolingo unit you've reached, and it writes the
entries. See [Vocabulary](#vocabulary) below.

### 6. First run, on your home Wi-Fi

```bash
uv run python -m server.main
```

It prints the address to use. Open it on the laptop first
(`https://localhost:8000`) and send a message to confirm the whole chain works
before involving the phone.

> The first startup takes ~15 s while the speech model loads, and the very
> first reply is slower while Ollama loads the model into memory. Later replies
> take a few seconds.

---

## Part 2 — Phone setup (client)

Do this once, at home, while both devices are on the same Wi-Fi. It is far
easier to sort out now than on a bus.

### 1. Open the page

With the server running, browse to the `https://<ip>:8000` address it printed.

### 2. Get past the certificate warning

The certificate is self-signed, so the browser will object. This is expected.

- **iPhone / Safari** — tap *Show Details* → *visit this website*.
- **Android / Chrome** — tap *Advanced* → *Proceed*.

### 3. If the microphone still doesn't work, trust the certificate properly

Safari in particular may accept the page but still refuse the mic. To fix it
permanently:

1. AirDrop `certs/cert.pem` from the laptop to the phone.
2. **Settings → General → VPN & Device Management** → install the profile.
3. **Settings → General → About → Certificate Trust Settings** → turn on full
   trust for `viet-practice local`.

Reload the page; the mic will now be allowed.

### 4. Grant microphone permission

Hold the 🎤 button. The browser asks for mic access — allow it. Speak a short
Vietnamese sentence, then release. Your words appear as text, and the reply is
spoken back.

> Speak *after* pressing, and hold until you've finished. A quick tap records
> too little audio and is rejected.

### 5. Optional: add to your home screen

- **iPhone** — Share → *Add to Home Screen*
- **Android** — menu → *Add to Home screen*

This gives it an icon and opens it without browser chrome.

### 6. Bookmark the offline address

During a trip the laptop's address will be **`https://192.168.2.1:8000`**, not
whatever your home Wi-Fi gave it. Bookmark that now — the certificate already
covers it.

---

## Part 3 — Using it offline

### Before you leave (needs internet only if updating vocabulary)

```bash
uv run scripts/vocab.py show     # confirm your words are loaded
```

### Set up the hotspot (once)

```bash
sudo ./scripts/setup_hotspot.sh
```

macOS Internet Sharing normally refuses to run without a connection to share.
The script creates a dummy loopback network service so it will broadcast with
no upstream at all, then prints these GUI steps:

1. **System Settings → General → Sharing** → the ⓘ next to *Internet Sharing*
2. **Share your connection from:** `AdHocSource`
3. **To devices using:** check **Wi-Fi**
4. **Wi-Fi Options…** → set a network name and WPA2 password
5. Toggle **Internet Sharing** on

### On the bus

1. Turn on Internet Sharing on the laptop.
2. **Start the server**, and only then — it reads the network interfaces at
   startup, so it must come up after the hotspot to print the right address:
   ```bash
   uv run python -m server.main
   ```
3. Join that Wi-Fi network from your phone.
4. Open `https://192.168.2.1:8000` and start talking.

Airplane mode on the phone is fine, as long as Wi-Fi is on.

---

## How a spoken turn works

Hold the mic → the recording is transcribed locally (faster-whisper, Vietnamese)
→ Ollama generates a reply grounded in your vocabulary file → the reply is
spoken with the macOS `Linh` voice.

- Replies may carry a short English gloss in parentheses. It is shown on screen
  but **stripped before speech**, so the Vietnamese voice never reads English.
- **Tap any reply to hear it again.**
- Conversations run about 10 exchanges per topic, then wrap up. *Chủ đề mới*
  starts a fresh one.
- Say you're stuck — "tôi không biết", "how do I say…" — and the server forces
  a teaching turn: you get a phrase plus a request to repeat it, and the
  conversation will not move on until you try.

---

## Vocabulary

`data/vietnamese_progress.json` decides what the agent talks about. It is
gitignored; `data/vietnamese_progress.example.json` shows the shape.

`strength` is what matters: **≥ 0.6** and the agent uses the word freely,
**below 0.6** and it deliberately works the word into conversation for practice.

```bash
# add or update words; missing translations and examples are generated locally
cat <<'JSON' | uv run scripts/vocab.py add
[{"vi": "chợ", "en": "market", "strength": 0.4}]
JSON

uv run scripts/vocab.py show      # counts, and which entries are incomplete
uv run scripts/vocab.py enrich    # fill gaps left by earlier runs
```

Re-running is safe — entries merge by word. A running server needs no restart;
the file is re-read on every message.

**Why this isn't synced from Duolingo:** Duolingo has no official public API,
the unofficial Python client has been broken since around 2023 (both login and
vocabulary endpoints fail), and the Duolingo MCP servers that exist return
profile, streak, and skill-completion data but no word list. So vocabulary is
supplied directly instead.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Mic button does nothing, or "mic is blocked" | The page isn't on trusted HTTPS. Run `./scripts/make_cert.sh`, then trust the cert on the phone (Part 2, step 3). |
| Banner shows no LAN address | Hotspot or Wi-Fi is off. Turn on Internet Sharing, then restart the server. |
| Phone can't load the page | Wrong address — use the one the banner prints. On the hotspot it's `192.168.2.1`, not your home IP. Also check macOS Firewall isn't blocking incoming connections. |
| Certificate warning after switching networks | The cert lists specific IPs. Re-run `./scripts/make_cert.sh` and reload. |
| First reply takes ~20 s | Ollama is loading the model into memory. Subsequent replies are much faster. |
| "Giữ nút lâu hơn" (hold the button longer) | The recording was too short. Press, speak, then release. |
| Agent uses words you don't know | Your vocabulary file is thin. Add more with `scripts/vocab.py` — conversation quality depends heavily on it. |

---

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | The phone client |
| `GET /health` | Liveness check |
| `POST /chat` | Text turn — `{message, session_id}` |
| `POST /voice` | Spoken turn — multipart `audio`, `session_id` |
| `POST /speak` | Vietnamese text → WAV |
| `POST /session/reset` | Start a new topic |

```bash
curl -k -X POST https://localhost:8000/chat \
  -H "Content-Type: application/json" -d '{"message":"Xin chào"}'
```

---

## How it fits together

```
Phone (browser)                     Laptop
  hold mic ──── audio ─────────────► faster-whisper  (speech → text, local)
                                            │
                                            ▼
                                     Ollama qwen2.5   (reply, local)
                                            │  grounded in
                                            │  vietnamese_progress.json
                                            ▼
  speaker ◄──── WAV ────────────────  macOS "Linh"    (text → speech, local)

        Wi-Fi broadcast by the laptop — no internet, no cell signal
```

Every box runs on the laptop. Nothing leaves the machine.
