# Value realization plan: adopting `agent-commerce-mandates-lab`

> **Important notice**
>
> - **Fictional buyer.** Casa Faro is a company invented for this lab. Mercado Ficticio and Bazar Inventado are invented merchants. Nothing here names a real client or employer.
> - **Inspired by the AWS Business Value Realization (BVR) framework:** a value-realization plan, KPIs with a threshold at each stage, and confirmation by the buyer. **It is not an official AWS template** (the official template is not public). The AWS BVR Competency is awarded to AWS partner companies, not to individuals, and it is not claimed here.
> - **Labels used in this file.** No other label is used.
>   - **MEASURED**: a figure this repo records, with the command or report and the date.
>   - **[EST]**: an explicit assumption. The labor inputs are the ones [docs/BUSINESS_CASE.md](BUSINESS_CASE.md) already marks [EST]. Hours, rates, the 52-week year, and the model ceiling below are further assumptions, marked on each row.
>   - **[SYN]**: a synthetic schedule for the stages. It is not a committed timeline.
>   - **SIMULATED**: catalog money in `LAB` cents, and the stub token price. The repo calls that price synthetic. Source: [docs/COST.md](COST.md) and `src/agent_commerce/pricing.py`. It is not a vendor bill.
>   - **UNVERIFIED**: named, and not measured in this repo.
> - Stub suite, demo, and forced regression stay attributed to **2026-10-18**, package **0.1.0**, model `stub-llm-v1`. They were not re-run for this document.
> - The native live sample stays attributed to [docs/live/native_5x/REPORT.md](live/native_5x/REPORT.md). The report is dated **2026-10-19**. Five passes, one model (`grok-4.20-0309-non-reasoning`), one prompt. Median **30/38**. Total **US$0.7127**.
> - Pytest was re-measured on **2026-10-22**. See the README Proof subsection and section 9 below.

This plan uses the same buyer and the same labor inputs as [docs/BUSINESS_CASE.md](BUSINESS_CASE.md). It does not invent a second volume of orders.

---

## 0. What the lab actually does (technical base)

A shopping agent may search and build a cart. Capture runs only when a signed mandate still fits the checkout: cap, expiry, merchants, categories, and per-item max. Above a threshold, a simulated person confirms. The model does not set the amount, does not choose the idempotency key, and does not approve. Prices in the catalog are SIMULATED `LAB` cents. The office mandate in `src/agent_commerce/mandate.py` is cap **20000**, human line **5000**. The grocery template is cap **10000**, human line **4000**.

**Stub suite, MEASURED, 2026-10-18**, package 0.1.0, command `.venv/bin/python -m agent_commerce.evalkit run`:

| Slice | Passed | Checker mean | Threshold |
|---|---:|---:|---:|
| Happy / edge / adversarial | 12/12, 17/17, 9/9 | 1.00 | 1.00 |
| All | **38/38** | **1.00** | **1.00** |

Tokens **56984** in / **2952** out. Suite cost **10302 micro-USD**, SIMULATED stub price.

One demo purchase the same day, empty work directory: **1** charge, **3600** SIMULATED LAB cents, **0** human approvals, **1509** in / **79** out, **273 micro-USD**. A second run on the same directory kept **1** charge and measured **1505** in / **79** out, still **273 micro-USD**.

Forced regression the same day, command `.venv/bin/python -m agent_commerce.evalkit regression`: exit non-zero, **0/1**, checker mean **0.90**, **40** in / **30** out, **24 micro-USD**. The cassette claims a gift card and calls no tool. The ledger stays empty.

**Native live sample, MEASURED.** Five passes on this repository's own client (`python -m agent_commerce.evalkit eval-live`, `LIVE_ENABLED=1`). Report dated 2026-10-19. Passed: **30, 30, 30, 30, 29** of 38. All 38 cases ran in each pass (**190** case runs).

| | min | median | max |
|---|---:|---:|---:|
| Passed (of 38) | 29 | **30** | 30 |
| Spend (US$) | 0.1252 | **0.1298** | 0.1745 |
| Model calls | 259 | 267 | 268 |
| LLM p50 (s) | 0.58 | 0.59 | 0.81 |
| LLM p95 (s) | 2.52 | 2.56 | 2.76 |

Five-pass total **US$0.7127**. Passes 2–5 spent **US$0.5550**. Pass 1 is **US$0.1577** in that report (the earlier one-pass write-up of the same pass says **US$0.1578**). One bill, inside the total. The scratch-adapter sample is a different bill, **US$0.2842**, and is not added here.

Safety counts on all five passes: unauthorized spend **0**, double charge **0**, action without approval **0**, injection obeyed **0**, secrets or PAN in the logs **0**. `raise_mandate_cap` after a prior rejection, repo definition: **16, 15, 13, 16, 14** (min **13** / median **15** / max **16**). Every raise call was refused. The cap did not move.

`no_false_purchase_claim` failed **4, 3, 3, 4, 6** times. **22** cases passed in all five passes. **16** distinct cases failed at least once. **4** cases failed in all five. The pass rate is an expectation match for this sample. Detail stays in the report and in the README live section.

CI does not call a hosted model. The default path has no vendor spend.

---

## 1. Problem and buyer

**Buyer.** Casa Faro (fictional) buys office supplies. A person still builds the cart. Household groceries are a second scenario on the same code, not a second buyer.

**Problem.** An assistant can spend outside the rules a person thought they set: over the cap, at the wrong merchant, twice on a retry, or because a product description told it to. A happy demo does not answer that. The lab signs the mandate and refuses capture when the signature fails or the checkout total does not fit.

The buyer in a real discovery would still answer who owns the cap, which merchants exist, and where the human line sits. Those questions are in [docs/DISCOVERY.md](DISCOVERY.md). The answers in that file are examples. They are not a transcript.

## 2. Value levers

1. **Buyer time on the cart** [EST]. The business case uses **6** minutes today and **1** minute when the assistant prepares the cart and a person only confirms above the line, so **5** minutes avoided. That difference is the labor lever. It moves if the person re-checks the cart.
2. **Capture refused outside the mandate.** Cap, merchant, category, per-item max, and an invalid signature. In the native sample those checks contributed **0** unauthorized-spend failures (MEASURED). The dollar value of one prevented capture is **UNVERIFIED**. This file does not price it.
3. **One charge when a payment is retried.** Double charge **0** on all five passes (MEASURED). On the replay cases the tool can accept `request_payment` twice and the ledger still keeps one charge.
4. **A person confirms above the line.** Office line **5000** SIMULATED LAB cents. The model has no approve tool. The share of real carts that would sit above the line is **UNVERIFIED**.

The labor lever is the only one with an [EST] dollar figure. The other three are the control. [docs/BUSINESS_CASE.md](BUSINESS_CASE.md) already says the case for the control is the avoided bad capture, and that the labor line is there so a conversation has a shape.

## 3. Objectives and sponsor

Roles, not named people. Titles beyond the repo's own words are marked.

- **Policy owner** signs the mandate. In this lab the process signs with a key it also holds. A real signature by a policy owner is **UNVERIFIED**. [docs/SCOPE.md](SCOPE.md) lists that signature as an exit criterion for a pilot, and it is not met.
- **The person who confirms** is outside the model. Above the line, the harness writes the approve row. The model cannot.
- **Procurement owns the cap and finance owns the instrument** is the split in discovery question 1. This repo runs both inside one process, which the discovery file allows only because both sides are fake.
- **Sponsor title** "head of procurement" is **[SYN]**. The repo does not name a sponsor.

Objectives:

- O1. Capture only inside a verified mandate. The stub gate and the live safety counts are the lab evidence (MEASURED). A real desk is **UNVERIFIED**.
- O2. A retry writes one charge, not two (MEASURED in the sample and in the stub idempotency cases).
- O3. Above the line, a person who is not the model confirms (implemented here with a simulated approver).
- O4. Buyer time moves from 6 minutes to 1 minute [EST]. **UNVERIFIED** until someone times real carts.

## 4. Baseline versus target KPIs

| KPI | Category | Baseline | Target | How it is measured | Stage |
|---|---|---|---|---|---|
| Cassette gate | Operational | **38/38**, checker **1.00**, 2026-10-18, package 0.1.0 (MEASURED) | 38/38 on the cassette command, checker mean at the threshold **1.00** | `.venv/bin/python -m agent_commerce.evalkit run` | Lab (done for that command) |
| Forced regression | Operational | Exit non-zero, **0/1**, checker **0.90** (MEASURED) | The command keeps exiting non-zero | `.venv/bin/python -m agent_commerce.evalkit regression` | Lab |
| Unauthorized spend | Risk | **0** across five passes / 190 case runs (MEASURED) | **0** on any later sample, and on real checkouts | The spend checks named in the five-pass report | Lab sample recorded. Real checkouts **UNVERIFIED** |
| Double charge | Risk | **0** (MEASURED) | **0** | `no_double_charge` plus the ledger | Lab sample recorded. Real rail **UNVERIFIED** |
| Expectation match, native client | Quality (not a score) | Median **30/38**, min 29, max 30 (MEASURED) | No numeric target. A higher rate on a new prompt would be a new sample | The five-pass report | Recorded. Using 30/38 as a model score is **UNVERIFIED** |
| Buyer minutes per order | Productivity | **6** [EST] | **1** [EST] | A timed sample of real carts. Empty today | Shadow, not started |
| Orders per week | Productivity | **40** [EST] | Unchanged until the buyer replaces it [EST] | The buyer's own count. Empty today | Discovery |
| Escalations | Agility | Empty. Office line is 5000 SIMULATED LAB cents | Defined in [docs/METRICS.md](METRICS.md), no number | Approve rows on real checkouts | **UNVERIFIED** |
| Completed within mandate, real orders | Risk | Empty. No real orders | Defined in METRICS, no number | Orders whose capture matched a verified mandate | **UNVERIFIED** |
| Cost per completed office order | Cost | Not measured. US$0.7127 is the five-pass bill, not this KPI | No target in the repo | Model bill plus the person's minutes, per captured order | **UNVERIFIED** |
| Pytest line coverage | Engineering | **50 passed**, line coverage **94.75%**, 2026-10-22, Python 3.12.3 (MEASURED). See section 9 | Floor in `pyproject.toml` is 80% | `.venv/bin/python -m pytest --cov` | Re-measured for this doc |

The repo measures the stub gate, the forced regression, the demo charge, and one five-pass live sample. It does not measure minutes, a real escalation rate, or dollars saved.

## 5. Measurement plan

Stages follow [docs/SCOPE.md](SCOPE.md). Durations are **[SYN]**.

1. **Lab (this repository).** Already recorded.
   - Work that exists: stub merchant, signed mandate, fake rail, cassette gate, forced regression, opt-in live client.
   - *Exit already met on 2026-10-18 for the stub:* `make eval` passes the 38 cases, `make eval-regression` exits non-zero, an invalid mandate records zero charges, a repeated payment records one charge.
   - *Live sample, recorded, not an exit criterion for a pilot:* five passes, median 30/38, total US$0.7127, safety counts zero. One model, one prompt. A later live run is a new sample. CI does not run it.
2. **Shadow** [SYN: a few weeks, not scheduled].
   - Work: the agent may build carts. A person still places the order. Time the 6-minute and 1-minute assumptions on that person's carts.
   - The cassette suite is the only shadow this repo runs. A week of real carts is an exit criterion in SCOPE and is not met.
   - *Exit:* a written sample of minutes, zero captures by the agent, cassette gate still green, regression still red.
3. **One gated category** [SYN: after shadow, not scheduled].
   - Work: capture only inside a verified mandate, and a person who is not the prompt author confirms above the line. One category. New cases before a second category.
   - *Exit:* zero unauthorized captures and zero double charges on those checkouts, and an escalation count written down. SCOPE also asks for a named human backup who can void. That person is not named here.
4. **Retention** [SYN: later, not scheduled].
   - Work: re-read the [EST] inputs. Fill cost per completed order, which METRICS leaves empty. Partial refunds only if a pilot asks, and only with new cases first.
   - *Exit:* the empty rows in METRICS have a source, or they stay empty on purpose.

**Buyer confirmation.** At the end of a real stage, the policy owner would sign the mandate and keep the numbers with the eval report. That signature is **UNVERIFIED**. This lab signs with a key the same process holds, labelled NOT REAL.

## 6. ROI model [EST]

**Formulas.**

- Weekly labor = orders/week × minutes avoided / 60 × loaded USD/hour.
- Year labor = weekly labor × 52.
- ROI = (benefit − cost) / cost.
- Payback (months) = initial investment / ((benefit − recurring cost) / 12).

**Benefit assumptions.** Every factor is [EST].

| Input | Value | Where it comes from |
|---|---|---|
| Orders | 40 per week | [docs/BUSINESS_CASE.md](BUSINESS_CASE.md) [EST] |
| Minutes today | 6 | same [EST] |
| Minutes left | 1 | same [EST] |
| Minutes avoided | 5 | difference of the two rows [EST] |
| Loaded labor | 30 USD per hour | same [EST]. Not a wage quote |
| Weekly labor | 40 × 5 / 60 × 30 = **100 USD** | same figure the business case publishes [EST] |
| Weeks in the year | 52 | assumption in this file [EST]. The business case stops at one week |
| Base year benefit | 100 × 52 = **5,200 USD** | arithmetic on the rows above [EST] |

The business-case table rounds the hours to 3.33 and still prints 100. The unrounded product 40 × 5 / 60 × 30 is 100. This file uses **100 USD per week**.

The model bill is not inside that 100. US$0.7127 is not subtracted here and is not a saving. A prevented bad capture is not given a dollar value. That value is **UNVERIFIED**.

**Year-1 cost used in the formula** is the [EST] stack in section 7: initial **4,240** + recurring **2,600** = **6,840**. The MEASURED live bill and the SIMULATED stub prices are listed in that table and are **not** added into 6,840.

| Scenario | Benefit USD/year | ROI | Payback |
|---|---:|---:|---|
| **Base.** 5 minutes avoided [EST] | 5,200 | (5,200 − 6,840) / 6,840 = −1,640 / 6,840 ≈ **−24.0%** | 4,240 / ((5,200 − 2,600) / 12) = 50,880 / 2,600 ≈ **19.6 months**. Not inside year 1 |
| **Conservative.** 2 minutes avoided [EST]. The person still rebuilds most of the cart. Weekly labor = 40 × 2 / 60 × 30 = 40 USD. Year = 40 × 52 = 2,080 | 2,080 | (2,080 − 6,840) / 6,840 = −4,760 / 6,840 ≈ **−69.6%** | Monthly net is negative: (2,080 − 2,600) / 12. **Does not pay back** |
| **Minimum.** 0 minutes avoided [EST]. The person re-checks the whole cart | 0 | (0 − 6,840) / 6,840 = **−100%** | **Does not pay back** |

**Reading the table.** On these assumptions the published labor sketch does not pay for the [EST] adaptation cost in year 1. The result flips only if the benefit is larger than 6,840, which this file does not claim. Changing 40, 5, 30, 52, 80 hours, 50 USD/hour, or the 200 USD ceiling changes the percentages. They are arithmetic on placeholders.

What the measurements support, without this ROI, is the control: the stub gate at 38/38, and zero unauthorized spend and zero double charges in the five-pass sample.

## 7. Cost table [EST]

Measured and simulated rows are shown so they are not mixed into the year-1 stack. Only the [EST] rows enter the ROI.

| Item | Figure | Label | Notes |
|---|---:|---|---|
| Native five-pass sample, total | US$0.7127 | MEASURED | Report dated 2026-10-19. Five passes, median 30/38. Not a cost per office order. Not an input to the ROI |
| Median pass spend | US$0.1298 | MEASURED | Min 0.1252, max 0.1745. One pass is 38 scripted cases, not one office order |
| Passes 2–5 | US$0.5550 | MEASURED | Inside the US$0.7127 |
| Pass 1 in the five-pass report | US$0.1577 | MEASURED | Same pass as the one-pass write-up's US$0.1578. Do not add both |
| Scratch-adapter sample | US$0.2842 | MEASURED | Different sample, 2026-10-18. Not added to US$0.7127 |
| Stub suite, 38 cases | 10302 micro-USD | SIMULATED | 2026-10-18. Synthetic rate, not a vendor bill |
| One demo purchase | 273 micro-USD | SIMULATED | 2026-10-18. Same rate |
| Forced regression | 24 micro-USD | SIMULATED | 2026-10-18 |
| Shadow, buyer time | 8 × 30 = **240** | [EST] | 8 hours is an assumption in this file. 30 USD/hour is the business-case rate. Initial |
| Adapt one category (catalog map, approver identity, cases) | 80 × 50 = **4,000** | [EST] | Both factors are assumptions in this file. 50 USD/hour is not a wage quote. Initial |
| Maintenance | 4 × 50 × 12 = **2,400** | [EST] | 4 hours/month and 50 USD/hour are assumptions in this file. Recurring |
| Hosted-model ceiling for a pilot year | **200** | [EST] | A ceiling for the formula. Not US$0.7127 scaled by 40 orders × 52 weeks. Recurring |

Initial investment [EST] = 240 + 4,000 = **4,240**. Recurring [EST] = 2,400 + 200 = **2,600**. Year-1 cost in section 6 = **6,840**.

Default path of this repo, including CI: **zero** vendor spend (MEASURED as a property of the commands, not as a pilot forecast).

## 8. Risks

Probability words below are the judgments already in [docs/RISKS.md](RISKS.md), or a pointer at the sample. They are not a measured incident rate.

| Risk | Source | What this plan does with it |
|---|---|---|
| A reader treats 100 USD/week [EST] as a saving | RISKS R14 | Section 6 keeps the labor line and shows year-1 ROI about −24% on the base assumptions |
| The five-pass median 30/38 is read as a model score | The report. Five passes, one model, one prompt. Which cases fail moves (16 distinct cases failed at least once) | No target pass rate in section 4. A new run is a new sample |
| Safety zeros are read as proof a rare miss cannot happen | README on the same sample. 190 case runs | Quoted as evidence for that sample. A real instrument is out of scope |
| The model calls `raise_mandate_cap` after a refusal (median 15 occurrences) | MEASURED. Every raise call was refused. The cap did not move | The cap stays inside the signature |
| Lab HMAC is mistaken for a verifiable credential | RISKS R3 | ADR 0001. The key is labelled NOT REAL. This is not an AP2 or UCP implementation |
| A retry double-charges | RISKS R4. The sample's double-charge count is 0 | Idempotency key, tested on the fake rail. A real processor is not in this repo |
| Pass 1 is added twice, or the scratch sample is added to the native total | README. US$0.1578 is inside US$0.7127. US$0.2842 is a different bill | Section 7 lists them as separate rows |
| The [EST] hours, the 50 USD/hour rate, 52 weeks, and the 200 USD ceiling are wrong | Assumptions in this file | Replace them with discovery answers. The percentages move with them |
| Dollar value of one bad capture | **UNVERIFIED**. Not in the business case as a number | Left out of the ROI on purpose |

## 9. What is MEASURED vs not

**MEASURED**

- Stub gate **38/38**, checker mean **1.00**, tokens 56984 / 2952, **10302 micro-USD** SIMULATED price. 2026-10-18, package 0.1.0, `evalkit run`.
- Demo: 1 charge, 3600 SIMULATED LAB cents, 0 approvals, 273 micro-USD. Second run on the same directory: still 1 charge, 1505 / 79, 273 micro-USD. 2026-10-18.
- Forced regression: non-zero exit, 0/1, checker 0.90, 24 micro-USD. 2026-10-18.
- Native live sample: five passes, results 30, 30, 30, 30, 29 of 38, median **30/38**, total **US$0.7127**, median pass spend **US$0.1298**. Safety counts 0. Report dated 2026-10-19. [docs/live/native_5x/REPORT.md](live/native_5x/REPORT.md).
- Pytest, re-measured **2026-10-22**, package 0.1.1, Python **3.12.3**, pytest **9.1.1**. Command `.venv/bin/python -m pytest --cov` with the addopts in `pyproject.toml` (`--cov=agent_commerce --cov-report=term-missing --cov-fail-under=80`). **50 passed.** Line coverage **94.75%** (2002 of 2113 statements; `percent_statements_covered` 94.7468054898249). The same run printed `Total coverage: 92.26%`. That total includes branches because `branch = true`. It is not the line figure. A repeat printed the same 50 passed and the same 92.26% total. The first run also printed `CoverageWarning: Module agent_commerce was previously imported, but not measured`. The repeat did not. Statement counts stayed 2002 of 2113. `src/` and `tests/` are the tree at `53577b5`. The docs change that adds this file does not edit them. Earlier live reports say 50 passed and do not record coverage or a Python version.

**[EST], not measured**

- 40 orders/week, 6 minutes, 1 minute, 5 minutes avoided, 30 USD/hour, 100 USD/week.
- 52 weeks, the 5,200 USD year figure, and the base / conservative / minimum ROI percentages.
- 8 hours, 80 hours, 4 hours/month, 50 USD/hour, the 200 USD ceiling, and the 6,840 USD year-1 cost.
- The conservative case of 2 minutes avoided.

**[SYN]**

- The stage durations in section 5. They are a shape for the plan, not a schedule anyone has agreed.

**SIMULATED**

- `LAB` cents, including the 3600 demo total, the 20000 office cap, and the 5000 office human line.
- Stub micro-USD at the rate in `pricing.py` (0.15 USD and 0.60 USD per million tokens, invented for the lab on 2026-10-18).

**UNVERIFIED**

- Minutes on a real desk, orders per week at a real desk, escalation rate, completed-within-mandate on real orders, cost per completed office order.
- The dollar value of one prevented bad capture.
- A policy owner signing the mandate, a named human backup, a week of shadow on real carts.
- Any claim that median 30/38 would hold for another model, another prompt, or another day.
- Python version and coverage for the 2026-10-18 stub run. This file does not invent them. The Python version above belongs to the 2026-10-22 pytest run only.
