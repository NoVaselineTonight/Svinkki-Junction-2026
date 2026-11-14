# Putting the demo online

Written 14 Nov 2026 by agent-d. What is in the repository for this, what the owner has to do once in a
browser, how to switch the API key, and what a public address changes.

It is deployed at https://svinkki.onrender.com from `main` via Render, on the free plan: 0.1 CPU, and it sleeps
after 15 idle minutes (about a minute to wake). Use a paid instance for the judging hours (see "Plan" below). In
public mode each visitor gets a private copy of the persona's state; see "What a public address changes". The
history of what was run before the first deploy is listed at the end.

## What gets deployed

One container: the app (`app/`, `web/`), the hosted entry point (`deploy/serve.py`) and a demo database that
is built while the image is built. No key and no dataset file is in the repository or in the image.

| File | Role |
|---|---|
| `Dockerfile` | Builds the image: fetches the dataset, builds the database, copies the app. Runs as an ordinary user. |
| `.dockerignore` | Only `app/`, `web/` and `deploy/` enter the build. |
| `render.yaml` | Blueprint for Render: one web service from the Dockerfile, redeployed on every push to `main` once the checks pass. |
| `deploy/serve.py` | `python -m deploy.serve`: listens on the host's `PORT`, caps the AI model's daily use, removes "Reset demo" in public mode. |
| `deploy/build_data.py` | `python -m deploy.build_data`: the demo database from the organisers' public dataset. |
| `deploy/removed_customers.txt` | The 286 customers the team leaves out, so the hosted database equals the team's own. |
| `deploy/check_key.py` | `python -m deploy.check_key`: does the configured key work? |
| `.github/workflows/deploy-image.yml` | Builds the image on GitHub and clicks through it. Run by hand, or when the Dockerfile or the data build changes. |

## Deploy from GitHub (Render)

Render builds the Dockerfile straight from the GitHub repository; a private repository works once Render's
GitHub app is allowed to read it. These steps need the owner's own accounts and are not done:

1. Sign in at https://render.com with GitHub and allow it to read `NoVaselineTonight/Svinkki-Junction-2026`.
2. New > Blueprint > choose the repository. Render reads `render.yaml`.
3. It asks for `ANTHROPIC_API_KEY`: paste the key for the public demo (see "Switching the API key").
4. Create. The first build takes several minutes (it downloads about 360 MB and builds the database).
5. The address is `https://svinkki.onrender.com` or similar: open it, pick Veeti, ask about taxis last
   month. The answer must say €92.85.

After that every push to `main` redeploys when the pull request checks have passed
(`autoDeployTrigger: checksPass`).

Plan: the blueprint asks for the free plan (0.1 CPU, 512 MB). A free service sleeps after 15 idle minutes and
takes about a minute to wake, and it is slow on the questions that need several tools. For the judging hours
change the plan in Render's dashboard to a paid instance and change it back afterwards.

Any other host that runs a Dockerfile works the same way (Fly.io, Railway, Koyeb, Google Cloud Run, a VM):
build the image, set the variables below, expose the port. Without Docker, on any machine with Python 3.13:

```bash
python -m deploy.build_data --out data/svinkki.db
```

```bash
PORT=8000 SVINKKI_PUBLIC=1 ANTHROPIC_API_KEY=... python -m deploy.serve
```

## Settings on the host

| Variable | Set to | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | the key | Turns the AI model on. Stored only in the host's secret store. |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Or `claude-sonnet-5-5` (about twice as fast) or `claude-haiku-5-5` (cheapest). |
| `SVINKKI_AI_DAILY_TURNS` | `400` | Customer questions a day (UTC) the model may answer. After that the built-in rules answer and the reply says the AI is offline. `0` switches the model off, `off` removes the cap. |
| `SVINKKI_PUBLIC` | `1` | Removes the "Reset demo" endpoint, which would let any visitor wipe everybody's demo state. |
| `PORT` | set by the host | The app listens on all addresses when this is set, otherwise only on 127.0.0.1. |
| `SVINKKI_DEMO_POOL` | build argument, `300` | Customers kept for "Try as a random customer". `0` keeps all 2,159 (about 540 MB). |

What the model costs: other agents measured about 0.013 to 0.034 US dollars per question on Opus 5.5 on
14 Nov, so 400 questions a day is roughly 5 to 14 dollars at most.

## Switching the API key

The app reads the key on every request, so a switch needs no code change and, locally, no restart.

Where the key is read from, first match wins: the `ANTHROPIC_API_KEY` environment variable (or `.env`), then
the one-line file `claude_api_key.txt` (git-ignored; written by Settings > "AI model (demo setup)").

To switch:

1. Create the new key at https://console.anthropic.com (Settings > API keys). For the public demo make it a
   separate key, in its own workspace with a monthly spend limit, so that the worst a stranger can do is use up
   that limit.
2. Hosted copy: in the host's dashboard change `ANTHROPIC_API_KEY` and save; the service restarts with the new
   key (on Render: the service > Environment). Nothing is committed.
3. This computer: either Settings > "AI model (demo setup)" in the app (paste, "Test the key"), or replace the
   single line in `claude_api_key.txt`. If `ANTHROPIC_API_KEY` is set in `.env` or the shell, change it there
   too: it wins over the file.
4. Check it:

```bash
python -m deploy.check_key
```

   It sends one tiny request and prints whether the key works, with which model, and only the key's last four
   characters. `--no-call` only says where the key comes from.
5. Revoke the old key in the console. The key in use until now was pasted into an AI chat on 13 Nov
   (`HANDOFF.md`), so revoke it whatever else happens.

Checked on 14 Nov: no real key is in the git history, in any tracked file or in the agents' chat (issue #1).
The only key-shaped string anywhere is a placeholder in a test.

## The data

The challenge dataset is not stored here. `deploy/build_data.py` downloads it from the organisers' public
repository (https://github.com/hackjunction/Junction-2026-S-pankki), checks the 363 MB transactions file
against the size and SHA-256 in its Git LFS pointer, leaves out the 286 customers in
`deploy/removed_customers.txt`, runs the normal `app.ingest`, and then keeps the transactions of the six demo
customers and 300 others for the random login. The group statistics are computed from all 4,814 customers
before that, so comparisons do not change. The result is 42 MB instead of 540 MB.

The build depends on the organisers' repository staying reachable, and each fresh download uses their Git LFS
bandwidth. The Dockerfile keeps the download in its own step so a rebuild reuses it when the host caches
build steps. If the download ever fails, build from files on disk instead:

```bash
python -m deploy.build_data --source-dir /path/to/the/organisers/csv/files --out data/svinkki.db
```

`--source-dir` wants the organisers' unfiltered files, not the team's filtered folder.

## What a public address changes

- **Each visitor gets a private copy of the persona.** Conversations, goals and notes belong to the visitor's
  session, so logging out and in starts fresh. (The audit found state shared per customer; the per-visitor copy
  was added in the demo-ready run on 14 Nov. Verify it on the deployed copy: log in as Veeti in two browsers
  and check that one does not show the other's notes.)
- **State is forgotten** when the host restarts the service (on a free plan, after every sleep).
- **There is no "Reset demo"** in public mode (the endpoint is removed). The audit found the button still shown
  in Settings; check whether it is hidden now. To start clean, log out and log in again.
- **The key setup in Settings is unreachable** from the internet (the app refuses it through a proxy): the key
  is changed on the host.
- **Anyone can ask questions**, so the daily cap above is the protection against cost, together with the
  spend limit on the key itself.
- The login is a demo picker and the data is synthetic. Nothing personal is on the server.

## For the Junction submission

- Demo link: the hosted address.
- The repository is private; the judges need either access or a public repository. Making it public also
  publishes the agents' chat in issue #1.
- `submission/SUBMISSION.md` holds the form text; its demo-link field is to be filled once the address exists.

## What was run, and what was not

Run on 14 Nov on the owner's computer:
- `python -m deploy.build_data` end to end from the organisers' repository: 91 seconds; the personas, the
  group statistics and every transaction of the six demo customers are identical to the team's database.
- `python -m deploy.serve` on that 42 MB database without a key: login as Veeti, "How much did I spend on
  taxis last month?" gives €92.85, receipts answer as before, random login works, "Reset demo" answers 404.
- The unit tests in `tests/test_deploy.py`.

Run on GitHub (workflow "demo image", pull request 41, 14 Nov):
- The image built from the Dockerfile in 1 minute 48 seconds, the database inside it in 51 seconds.
- Started without a key, it listed the six demo customers, answered Veeti's taxi question with €92.85 from the
  built-in rules, refused "Reset demo" with 404 and ran as the user `svinkki`, not root.

Not run at the time of writing (before the first deploy; it is deployed now):
- Docker is not installed on the owner's computer, so the image has only been built on GitHub.
- `render.yaml` had not been read by Render.
- The hosted entry point had not been run with a real key.
