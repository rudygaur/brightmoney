# KYC Funnel Analysis

A synthetic dataset of 2.5 million US fintech sign-ups, loaded into Postgres and analysed to answer
one question: **why aren't all real users getting identity-verified, and what's the biggest fixable
cause?**

This is a take-home case study (see [the brief](APM%20KYC_Design_Project_Assignment_Instructions.md)),
not a production codebase — the SQL and notebooks exist to make the analysis's numbers reproducible
and defensible, not to ship anywhere. Everything here works the same regardless of what kind of
Postgres you point it at (Docker, or a native install) — see **Setup** below.

**Headline finding (Task 1):** 7.93% of users aren't verified against a 5% target, and just over
half of that gap is a single routing bug — 101,201 people who failed the first identity check and
were simply never given a second one. Full story, with charts:
**[Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018)**.

**The fix (Task 2):** a redesigned waterfall that makes that routing failure structurally
impossible — every check outcome gets a defined next step, and nobody exits without either verifying
or being seen by a human. It also closes a sanctions/PEP visibility gap the current design has no way
to measure. Full story: **[The Waterfall, Rebuilt](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d)**.

## Start here, depending on what you want

| I want to... | Go to |
|---|---|
| See why users fail, as charts, no setup required | **[Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018)** (Task 1 report) |
| See the fix, as a diagram, no setup required | **[The Waterfall, Rebuilt](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d)** (Task 2 report) |
| Get the numbers and reasoning without opening a notebook | [IMPORTANT.md](IMPORTANT.md) — one-page cheat sheet |
| See exactly how the data was loaded and cleaned, and why | [AUDIT_LOG.md](AUDIT_LOG.md) — full decision trail |
| Read the redesign's full logic and cost trade-offs | [TASK2_WATERFALL_DESIGN.md](TASK2_WATERFALL_DESIGN.md) |
| Run the SQL myself / verify a number | Set up Postgres below, then run the notebooks |
| Understand working conventions for this repo | [CLAUDE.md](CLAUDE.md) |

## What's in here

```
KYC_Synthetic_Dataset.csv                    the raw data (272 MB, not committed — see .gitignore)
notebooks/
  01_kyc_load_and_setup.ipynb                loads the CSV into Postgres, cleans it, validates it
  02_task1_funnel_analysis.ipynb             the funnel analysis itself, in plain English + SQL
AUDIT_LOG.md                                 every loading/cleaning decision, defect, and caveat
IMPORTANT.md                                 one-page summary: numbers, traps, judgement calls
TASK2_WATERFALL_DESIGN.md                    the redesigned waterfall: logic, stop conditions, cost
.env.example                                 copy to .env and fill in your Postgres connection
```

Two Postgres tables matter:

| Table | What it is |
|---|---|
| `kyc.kyc_raw` | The CSV loaded verbatim — every column text, nothing cleaned. Reference only. |
| `kyc.kyc_users` | The cleaned, typed, indexed table. **This is what the analysis runs on.** |

## Setup — works with Docker or a native Postgres install

The notebooks connect over an ordinary TCP connection and never ask the Postgres *server* to read a
local file — the CSV is streamed in from the notebook itself. That one design choice is what makes
the exact same code work whether Postgres is in a container or installed directly on your machine:
neither approach can assume the server process can see your files, so neither has to.

**1. Get a Postgres server running — pick one:**

- **Docker** (simplest if you don't already have Postgres):
  ```bash
  docker run -d --name postgres -e POSTGRES_PASSWORD=changeme -p 5432:5432 postgres
  ```
- **Native install** — [Postgres.app](https://postgresapp.com/) (macOS), `brew install postgresql`
  (macOS), or your OS package manager (Linux). Start the service however that install method
  documents (Postgres.app: open the app; Homebrew: `brew services start postgresql`).

Either way, you need a database for this project to live in — it does **not** get created for you,
since it might be one you already use for other things:
```sql
CREATE DATABASE study;
```

**2. Configure the connection:**
```bash
cp .env.example .env
# edit .env — uncomment the block matching Docker or native, fill in your values
chmod 600 .env
```

**3. Install the Python environment and run:**
```bash
python3 -m venv .venv
.venv/bin/pip install "psycopg[binary]" pandas sqlalchemy ipykernel jupyterlab python-dotenv
.venv/bin/python -m ipykernel install --user --name brightmoney-kyc --display-name "Python 3 (Brightmoney KYC)"
.venv/bin/jupyter lab notebooks/01_kyc_load_and_setup.ipynb
```

Run `01_kyc_load_and_setup.ipynb` top to bottom first (loads and validates the data — a few minutes
for a 2.5M-row CSV), then `02_task1_funnel_analysis.ipynb` (read-only, just queries). Both notebooks
are idempotent: re-running rebuilds cleanly rather than erroring or duplicating.

**Already have a database and just want to point at it?** Set `PGDATABASE` in `.env` to that
database's name — the notebooks create their own `kyc` schema inside it and refuse to touch any
table there they didn't create themselves, so it's safe to share with other work.

## A note on the numbers

Every figure in `IMPORTANT.md`, `AUDIT_LOG.md`, and the published report is computed live by the
notebooks from `kyc.kyc_users` — nothing is hand-typed or estimated without saying so. If you re-run
the notebooks, you should get the identical figures back; if you don't, something about the setup
differs from what's documented here, and that's worth chasing down before trusting any downstream
number.

---

*Built with [Claude Code](https://claude.com/claude-code).*
