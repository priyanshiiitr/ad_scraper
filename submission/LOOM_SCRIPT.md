# Loom script

Record this yourself, screen plus voice, about four minutes. Import the workflow before you hit record so the first click is Execute, not a hunt through menus.

## 0:00 — the decision, before the tool

Say this while the PDF’s first page is on screen. Do not start with “today I will show you a workflow”.

> The best ad in the list is library ID 1112422725088441. It is the first card in the impressions sort, started 21 October, and the sentence is on 11 live cards, one of them since 8 April. Hook: “Speak English fluently with the power of AI.” Body asks for a ₹1 trial. The button I opened is Install Now, to the Play Store listing com.practice.ninja_study. The headline under the video is the Hindi line, “MySivi se shuru karo, sirf ₹1 mein.”
>
> I am not saying this is the best script. I am saying it is the control. India ads in this library do not show spend or the impression number. The sort is a rank, the start date is a fact, and a repeated sentence is a fact. I scored those. I did not ask a model to pick.

Point at the score table. Name the runner-up out loud: Kannada, 70, 15 minutes a day, no ₹1 in the text or in the two headlines you opened. Say the Monday test in one sentence: put the Tamil structure — price, 40 lakh, mother tongue, 15 minutes — into the Kannada first line, and do not brief another version of the English hook.

## 1:20 — sample run, no token

Switch to n8n. Config is visible. Mode is `sample`. Both keys still say PASTE.

> Sample mode scores the same 30 cards as the PDF. No Apify call, no Gemini call.

Execute. Open the last node, `Build the read`. Read the first three lines of `report_markdown` so they hear the same library ID and the same 85.

## 2:10 — why the model is second

Click `Score the pull` and show the code just long enough to say:

> The score is in this node. Gemini runs only if that key is not the placeholder. It can move a creative by at most 8 points, and only if it quotes a phrase that is already in the ad. A quote I cannot find is thrown away. The other submissions you have already seen ask the model which ad feels best. This one does not.

## 2:50 — the live path, without spending if the token is empty

Hover `Start Apify run`. Do not paste a token on camera.

> Live mode posts the assignment URL to Apify’s Facebook Ad Library actor, 12 ads, 1 GB, EU details off, no residential proxy. Twelve ads is under one cent at the published 75 cents per thousand. The free credit covers the Meet. If the run is still going after a minute, this poll asks again. Then the same score node runs.

If you do have a free-tier token and want to show a live run, paste it, set mode to `apify`, set `asOf` to today, execute, and narrate the wait. Stop once the read names a winner. Do not turn on a schedule.

## 3:30 — close on the action, not the stack

> What I would do on Monday is hold 1112422725088441, brief one Kannada opening that actually says ₹1 and 40 lakh, move the Bangla price into the first line, leave Marathi running, and open the PhysicsWallah card that came back inside this search before I scrape it again. The workflow is how that check happens next week without me retyping the table.

Stop. Don’t add a “thank you for this opportunity” outro.
