# DNA extraction demo script

All names, samples, measurements, inventory, and fallback messages below are
synthetic. This demonstration does not replace an institution's approved
protocol.

## Main script — about 2 minutes 40 seconds

| What the researcher says | What judges see/hear |
| --- | --- |
| **0:00 — Start by voice.** “Hey Jarvis. Start the DNA extraction demo, version 1.0.0. I am Synthetic Demo Operator, using synthetic kit lot SYNTHETIC-KIT-LOT-002 and samples SYNTHETIC-SAMPLE-11, SYNTHETIC-SAMPLE-12, SYNTHETIC-SAMPLE-13, SYNTHETIC-SAMPLE-14, SYNTHETIC-SAMPLE-15, and SYNTHETIC-SAMPLE-16.” | VoiceOS starts `dna-extraction-demo`; the dashboard shows the running protocol, operator, and six clearly synthetic sample IDs. If wake activation fails, use the VoiceOS shortcut and say that fallback is manual. |
| **0:18 — Ask the current step.** “What is the current approved-protocol step?” Then record setup metadata for `SYNTHETIC-SAMPLE-11` with condition `kit_lot` = `SYNTHETIC-KIT-LOT-002`, and say “Complete setup-metadata.” | VoiceOS attributes the instruction to the approved protocol, shows the required sample ID and kit lot condition, then advances to the observation step. |
| **0:38 — Record a normal observation.** “Record this observation for SYNTHETIC-SAMPLE-11: synthetic demo record appears normal.” Then: “Complete record-observation.” | The normal observation appears as a researcher-sourced, timestamped event. No interpretation is added. |
| **0:54 — Omit a unit.** “At measure-demo-signal, record 24 for SYNTHETIC-SAMPLE-11 using SYNTHETIC-INSTRUMENT-02.” | LabLoop does not guess: it asks which unit to record. This is the missing-metadata follow-up. |
| **1:08 — Supply an out-of-range value.** “Record that as 24 demo units using SYNTHETIC-INSTRUMENT-02 for SYNTHETIC-SAMPLE-11.” | The measurement is saved. VoiceOS says 24 is outside the approved inclusive range of 10–20 demo units, without diagnosis, cause, or remediation advice. |
| **1:25 — Ask a supervisor with context.** “Ask the supervisor: Should I record any additional context for this deviation?” | **LIVE SLACK:** the configured rehearsal channel receives the question with run and current-step context. The dashboard shows an attributed outbound supervisor event if the integrated build stores it. |
| **1:42 — Show the attributed reply.** “Check for replies in that supervisor thread.” | **LIVE SLACK:** show and attribute the real reply. **SIMULATED FALLBACK:** instead select the seeded completed run, show “Synthetic fallback reply,” and say: “This is a clearly labeled simulated reply, not live Slack.” Never present the fallback as live. |
| **1:58 — Consume inventory.** “Consume 3 demo units of synthetic-demo-reagent.” | Quantity moves from 12 to 9. Crossing the threshold creates one **pending restock request requiring human approval**; no purchase or approval occurs. |
| **2:15 — Show immutable history.** “Show the audit history.” | On the read-only dashboard, point to the live measurement and deviation. Then select the seeded synthetic historical run and show both the original observation and its correction linked by `supersedes_event_id`; the original remains visible. |
| **2:35 — Close.** “LabLoop keeps hands-busy research moving by joining approved protocol guidance, complete context, human supervision, and an immutable record in one voice workflow.” | Leave the protocol state, attributed messages, inventory warning, pending request, and immutable timeline visible. |

## Sixty-second backup

| What the researcher says | What judges see/hear |
| --- | --- |
| **0:00.** “Start the DNA extraction demo for Synthetic Demo Operator and six synthetic samples. What is the current approved-protocol step?” | VoiceOS starts the run by voice and shows protocol attribution, setup metadata, and the six samples. Use the manual VoiceOS shortcut if the wake word fails. |
| **0:12.** “Record a normal synthetic observation. Record 24 for SYNTHETIC-SAMPLE-11 using SYNTHETIC-INSTRUMENT-02.” After the follow-up: “The unit is demo units.” | LabLoop asks for the omitted unit, records the completed measurement, and flags the out-of-range value without diagnosis. |
| **0:28.** “Ask the supervisor whether more context should be recorded. Check for replies.” | Show the run/step-context question and an attributed **LIVE SLACK** reply, or announce and show the **SIMULATED FALLBACK** record. |
| **0:40.** “Consume 3 demo units of synthetic-demo-reagent.” | The dashboard shows a pending restock request requiring human approval—not an order. |
| **0:49.** “Show the audit history.” | Show the immutable original and correction trail, then close: “LabLoop joins approved guidance, context, human supervision, and an immutable record in one voice workflow.” |

## Pre-demo checklist

- Reinstall in a fresh virtual environment and run every verification command in
  ticket 10.
- Seed a fresh `.context/labloop-demo.db`; confirm it reports one synthetic run,
  one inventory item, and zero pending requests.
- Start the dashboard, load `http://127.0.0.1:8765`, and select the synthetic
  historical run to confirm its correction and simulated fallback labels.
- Start the MCP Custom App and confirm all ten tools appear in VoiceOS.
- Start a throwaway live run and verify the current step, observation, missing-unit
  follow-up, non-diagnostic range warning, and inventory threshold wording.
- Choose one supervisor path before judges arrive: **LIVE SLACK** with a person
  ready to reply, or **SIMULATED FALLBACK** with no claim of live service.
- Test the configured channel and bot scopes without displaying credentials.
- Test wake activation once; keep the normal VoiceOS shortcut ready.
- Test spoken output once; keep visible VoiceOS text as the explicit fallback.
- Reset the database immediately before the demo so inventory starts at 12 demo
  units and no pending restock request already exists.
