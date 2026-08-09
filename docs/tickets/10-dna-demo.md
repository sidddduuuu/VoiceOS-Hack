# Ticket 10 — DNA extraction demo protocol and rehearsal kit

## Outcome

Create credible, clearly synthetic demo data and an exact rehearsal script that
shows LabLoop's value in under three minutes. This ticket adds no production code.

## Start here

Read the MVP spec, protocol JSON rules in ticket 01, and all frozen contracts.
Use a generic educational/demo workflow; do not copy proprietary kit instructions
or claim the protocol is safe for real laboratory use.

## Owned files

- `protocols/dna-extraction-demo.json`
- `demo/seed.py`
- `demo/README.md`
- `demo/demo-script.md`
- `tests/test_demo_assets.py`

Do not edit any other file. Do not add dependencies, application logic, secrets,
real names, real sample identifiers, or actual researcher data.

## Demo protocol

Create one protocol with ID `dna-extraction-demo`, version `1.0.0`, and 6–8 concise
steps that exercise the product capabilities rather than teach wet-lab technique.
Include:

- setup metadata requiring a sample ID and kit lot condition;
- an observation step;
- at least one measurement requiring value, unit, instrument, and sample ID;
- an expected inclusive range that makes an intentional out-of-range demo value
  easy to understand;
- one timer step;
- one irreversible checkpoint explicitly labeled for confirmation;
- a final storage/documentation checkpoint.

Instructions must say they are demo placeholders and that the researcher follows
their institution's approved protocol. Do not provide hazardous quantities,
exposure parameters, diagnostic claims, or remediation advice.

## Seed script

`demo/seed.py` uses only stdlib plus merged LabLoop modules. It accepts:

```text
--db PATH       required target SQLite path
--reset         allow replacement only after explicit confirmation flag
```

Safety requirements:

- refuse an existing database unless `--reset` is supplied;
- reject directories, symlinks, and paths outside the current workspace;
- when reset is authorized, remove only the exact validated database file plus
  its `-wal` and `-shm` siblings;
- seed synthetic inventory and one optional completed historical run using public
  APIs where available;
- label all operators, samples, messages, and values as synthetic;
- never read Slack configuration or call a network service;
- print the resulting local paths and a compact record count.

Do not invent private methods just to seed. If merged APIs cannot create a required
display state, document the gap rather than editing their modules.

## Documentation deliverables

`demo/README.md` must include:

- fresh venv/install commands;
- seed, MCP server, dashboard, and optional wake-helper commands;
- exact VoiceOS Custom App launch command and UI path;
- required/optional environment variables with placeholder values only;
- Slack bot scopes/channels needed, without credentials;
- a clean fallback if Slack, wake word, or spoken output fails;
- cleanup instructions limited to explicit generated files.

`demo/demo-script.md` must be a timed 2–3 minute script with two columns: what the
researcher says and what judges see/hear. Include these beats:

1. start the DNA extraction demo by voice;
2. ask what step is current;
3. record a normal observation;
4. omit a unit and receive a follow-up;
5. provide an out-of-range value and get a non-diagnostic flag;
6. ask a supervisor with run/step context;
7. show a reply and attribution (live Slack or explicitly labeled fallback);
8. consume inventory and create a pending, human-approved restock request;
9. show the immutable dashboard/correction trail;
10. close with the product thesis in one sentence.

Add a sixty-second backup script and a pre-demo checklist. Never pretend a mocked
Slack reply or synthetic record is live.

## Tests

`tests/test_demo_assets.py` must verify:

- JSON parses and loads through `load_protocol` when ticket 01 is present;
- required demo IDs/version/step features exist;
- all synthetic identifiers are visibly synthetic;
- no likely secret patterns or real Slack tokens are present;
- seed reset rejects unsafe/external/symlink targets;
- documentation references the ten required demo beats and fallback labels.

## Acceptance criteria

- A teammate unfamiliar with the project can rehearse from the docs alone.
- The protocol demonstrates metadata follow-up, deviation, supervision, inventory,
  and audit history without offering scientific advice.
- Destructive seed behavior is explicit and narrowly scoped.
- Only the five owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_demo_assets -v
python -m json.tool protocols/dna-extraction-demo.json >/dev/null
python -m compileall -q demo/seed.py tests/test_demo_assets.py
git diff --check
git diff --name-only origin/main...HEAD
```

Run the seed against a disposable path inside the workspace and report the exact
command/result. Report which integrations were live versus explicitly simulated.
