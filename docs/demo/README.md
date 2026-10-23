# Demo

Screen recording: [agent_commerce_mandates_lab_demo_en.mp4](agent_commerce_mandates_lab_demo_en.mp4) (1 min 32 s, 1280×720). English narration. English subtitles are burned into the picture and also in [agent_commerce_mandates_lab_demo_en.en.srt](agent_commerce_mandates_lab_demo_en.en.srt). [agent_commerce_mandates_lab_demo_en.es.srt](agent_commerce_mandates_lab_demo_en.es.srt) is the same English text: the former Spanish sidecar, translated, with the same cue times. The video binary still contains the original Spanish soft track and was not edited.

The narration voice is synthetic (xAI TTS). The script that was spoken is [final_script_agent_commerce_mandates_lab_demo_en.md](final_script_agent_commerce_mandates_lab_demo_en.md). One pass, one model, one prompt.

## What the video shows

A real run of this repository, then the native measurement printed from logs. No new live eval was started for the recording. The offline scenes use the stub planner and do not call a hosted model.

1. A purchase inside the signed mandate. The take runs the demo command. The picture shows one charge, 3600 simulated LAB cents (`mandate_valid` true). The narration says "thirty-six LAB" and that LAB is simulated money.
2. Attack rows replayed with this repository's code and the stub planner: over the cap, wrong merchant, expired mandate, forged signature, a retried payment that stays one charge, a product description that asks for a gift card, a purchase above the human line, and a human refusal with no charge.
3. The offline gate: 38/38. A forced regression exits 1.
4. The native live card. One pass, 38 cases, model `grok-4.20-0309-non-reasoning`. Thirty cases passed. Spend US$0.1578. 267 model calls, every HTTP status 200. No unauthorized spend and no double charge. After a refusal, `raise_mandate_cap` was counted in 16 of 38 cases under the repo definition, and every raise was refused.
5. The spoken caveat: one pass, one model, one prompt. Eight cases missed: four loops with no spend, four outcomes that differed from the script.
6. Close. Phase one only. A processor and disputes are design only. The ROI line is the [EST] labor figure, about 100 USD a week, and the narration says it is not a saving.

The terminal text is the take under [evidence_agent_commerce_mandates_lab_demo/terminal_take/](evidence_agent_commerce_mandates_lab_demo/terminal_take/take.json). The live card is [evidence_agent_commerce_mandates_lab_demo/sources/live_native/](evidence_agent_commerce_mandates_lab_demo/sources/live_native/REPORT.md), the same files as [docs/live/native_v2/](../live/native_v2/REPORT.md).

## Where each number comes from

[evidence_agent_commerce_mandates_lab_demo/number_trace.md](evidence_agent_commerce_mandates_lab_demo/number_trace.md) maps each number in the picture and in the narration to its source. The live numbers come from that native measurement: [docs/live/native_v2/REPORT.md](../live/native_v2/REPORT.md) and [docs/live/native_v2/run1/summary.json](../live/native_v2/run1/summary.json). They are not the earlier scratch-adapter sample in [docs/live/REPORT.md](../live/REPORT.md). That card is the earlier one-pass archive. The current five-pass sample is [docs/live/native_5x/REPORT.md](../live/native_5x/REPORT.md). The video does not show it.

This measurement was run with this repository's own client at main `3c440b2`. Snapshot commit `36daf60` holds the same tree. The take's `git log` line is `df07496`, and the script says "Measured on an earlier commit than this snapshot." `df07496` is a later commit on this branch (docs and CI files). The measured code tree is the `36daf60` tree.

Pass rate on that card is an expectation match for this one pass. It is not a model score.

Other files in the evidence folder: [spend.md](evidence_agent_commerce_mandates_lab_demo/spend.md) (TTS and speech-to-text for the recording; no live model calls for the video), [stt_transcript.txt](evidence_agent_commerce_mandates_lab_demo/stt_transcript.txt), and [code/](evidence_agent_commerce_mandates_lab_demo/code/narration.json) (`narration.json`, `timestamps.json`).
