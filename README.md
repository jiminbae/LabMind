# LabMind

LabMind is a Streamlit application for registering laboratory reagents and
searching a reviewed chemical inventory. It combines optional Gemini assistance
with deterministic validation, storage rules, and SQLite-backed inventory data.

Live app: [tell-me-more-esea.onrender.com](https://tell-me-more-esea.onrender.com/)

## What it does

### Reagent intake

1. Upload a reagent-label image or enter the label fields manually.
2. Review the extracted chemical name, CAS number, manufacturer, lot number,
   container quantity, and volume per container.
3. Generate suggested chemical-function labels and storage constraints.
4. Review the deterministic storage recommendation and save the record.

Gemini can read label text and suggest allowlisted chemistry metadata, but its
output is always editable. CAS validation, record IDs, storage assignment, and
database writes are handled by application code rather than the language model.

### Inventory search

- **Basic filters** search by chemical name, CAS number, record ID,
  manufacturer, storage location, quantity, volume, and expiry state.
- **Natural-language query** interprets questions such as “Do we have ethanol?”
  and “Show all we have”
  as an allowlisted filter object, then verifies it against the actual
  inventory. Gemini never claims that an item is in stock by itself.
- Natural-language filters can target names, CAS numbers, manufacturers,
  storage locations, quantity, volume, expiry, availability, and reviewed
  chemical labels.
- Verified results can be exported as CSV.

## Technology

- Python 3.12
- Streamlit
- SQLite
- pandas
- Google Gemini through `google-genai`
- Render for deployment

The application entry point is `app.py`. The current interface is implemented
in `app_v5.py`, and backend services are organized under `backend/`.

## Repository structure

```text
LabMind/
|-- app.py                         # Streamlit and Render entry point
|-- app_v5.py                      # Current interface and user workflows
|-- backend/                       # Inventory, validation, and AI services
|   |-- app_service.py             # Interface-to-backend adapter
|   |-- db_init.py                 # SQLite initialization and migrations
|   |-- db_utils.py                # Validated database operations
|   |-- classification_service.py  # Chemical-function suggestions
|   |-- query_translation_service.py # Natural-language filter translation
|   `-- vision_service.py          # Reagent-label image extraction
|-- tests/                         # Unit, integration, and Streamlit tests
|-- schema.sql                     # SQLite schema
|-- render.yaml                    # Render deployment configuration
|-- requirements.txt               # Python dependencies
|-- .streamlit/                    # Theme and local secrets example
`-- .github/workflows/test.yml     # Continuous integration on main
```

Supporting backend modules handle CAS validation, classification caching,
provider configuration, intake, and deterministic safety rules.

## Run locally

Clone the repository and enter its directory:

```bash
git clone https://github.com/jiminbae/LabMind.git
cd LabMind
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependencies and start Streamlit:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Configure Gemini

Gemini is optional. Without a key, the app remains usable through manual entry.

For local development, copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and set:

```toml
LABMIND_VISION_MODE = "live"
LABMIND_PROVIDER = "gemini"
GEMINI_API_KEY = "your-key"
```

Never commit the API key. On Render, add the same values under the service's
Environment settings.

## Database and deployment

By default, LabMind stores records in the local `inventory.db` SQLite database.
Set `LABMIND_DB_PATH` to use another path.

The included `render.yaml` installs the dependencies, starts Streamlit on
Render's assigned port, and uses `/_stcore/health` as its health check. A free
Render instance has an ephemeral filesystem, so its local SQLite data can be
lost after a restart or redeployment. A production version should use a
persistent disk or an externally managed database.

## Tests

Run the complete test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The suite covers database initialization, reagent registration, CAS validation,
AI-provider boundaries, inventory filtering, natural-language routing, and
Streamlit regressions.

## How we used AI to build LabMind

We used ChatGPT and Codex as development partners, not as the source of product
truth. They helped us draft Streamlit components, trace data across the UI and
backend, refactor repeated code, propose tests, and investigate failures. We
reviewed the generated changes, ran the application, and used automated tests
before accepting them.

### A specific example

We asked AI to investigate why a natural-language question reported that a
chemical was missing even though the record existed in SQLite. AI helped trace
the path from the question parser to the generated filter and final dataframe.
This revealed that exact-name matching rejected abbreviations and
stereochemical prefixes such as `(R)-`, and that zero-quantity or expired named
records were hidden instead of being shown with their real status. We changed
the routing order, normalized names, returned explicitly requested records, and
added regression tests using real inventory rows.

### What AI got wrong

AI-generated code was not correct on the first attempt. One classification
implementation modified `st.session_state` after Streamlit had instantiated
widgets, causing a `StreamlitAPIException`. Another inventory view tried to
parse the text `Not recorded` as a date, causing a pandas `DateParseError`.
AI also suggested interface features that worked technically but did not support
the product's core task, including an Order stage and inventory charts. We
reproduced these problems, identified their causes, changed the code, and added
tests rather than accepting the first generated solution.

### What the team did ourselves

We wrote and reviewed the product requirements, workflow decisions, and safety
boundaries ourselves because AI cannot know our users or take responsibility
for laboratory decisions. The team decided that storage locations must come
from deterministic rules, that AI suggestions must remain editable, and that
inventory availability must come only from the database. We also decided to
remove the Order and Visualize sections after judging that they distracted from
the core intake-and-search workflow.

In short: **we used AI to implement, debug, and test; we did not let it decide
what the product should be or treat its output as automatically correct.**

## Team reflection

This project taught us that AI is most useful when it accelerates exploration,
implementation, and debugging without owning the final decision. We learned to
verify generated code at every frontend-backend boundary, involve teammates
when assumptions affect their work, and remove features that function
technically but do not create meaningful value for the user.
