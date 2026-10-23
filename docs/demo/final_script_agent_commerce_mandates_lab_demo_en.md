# Final script used: agent_commerce_mandates_lab_demo_en.mp4 (mand)

Voice: xAI TTS leo, speed 1.08. English narration is burned into the picture. The video file also has a Spanish soft subtitle track, disabled by default. That track is inside the video binary and was not edited. The sidecar caption file is English.


## A_hook (starts 0.80 s)

- A shopping agent that can spend, but only inside a signed mandate: a cap, an expiry, allowed merchants.
- First, a purchase inside the mandate.

## B1_inside (starts 10.52 s)

- One charge, thirty-six LAB. LAB is simulated money.

## B2_cases (starts 16.80 s)

- Now the attacks, replayed with the repo's own code and a stub planner.
- Over the cap: refused. Wrong merchant: refused. Expired: refused. Forged signature: refused.
- A payment retried: still one charge.
- A product description that orders a gift card: refused.
- Above the human line, a person confirms. If the person says no, nothing is charged.

## C_gate (starts 41.94 s)

- All thirty-eight offline cases pass.
- Force a regression, and the gate exits with one.

## D_live (starts 48.71 s)

- Now a real model: one pass, thirty-eight cases.
- Thirty pass, for sixteen cents. No unauthorized spend, no double charge.
- After a refusal, the model tried to raise its own cap in sixteen cases. Every attempt was rejected.

## E_caveat (starts 64.36 s)

- Caveats: one pass, one model, one prompt.
- Eight cases missed: four no-spend loops, four outcomes that differed from the script.
- Measured on an earlier commit than this snapshot.

## F_close (starts 76.90 s)

- Phase one only. A real pilot needs a human backup and real shadow carts. Not done.
- Processor and disputes: design only.
- ROI: E-S-T, about a hundred dollars a week of labor. Not a saving.
