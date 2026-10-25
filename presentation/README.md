# Litmus presentation demo

Separate, presenter-paced hot-water demonstration. The real station, worker and Next.js app in the rest of this repository are unchanged. This application does not call them, Gemini or any sensor endpoint, and needs no secrets or dependencies.

## Run / deploy

`cd presentation && npm start` opens http://127.0.0.1:18350. Run `npm test` for the flow tests. Deploy **this folder**, not the repository root: `npx vercel --prod` (project name `demo-litmus`, framework Other, output `public`). For a Git-connected Vercel project choose Root Directory `presentation`. Do not reuse the real system's Vercel project.

## Presentation flow

1. Introduce room-temperature reference A and hot-water preparation B.
2. Begin the paired run; show the baseline. Add iodine physically, then mark it added.
3. Wait while the physical reaction develops. Nothing advances automatically.
4. Reveal the expected difference when ready: darker reference, paler heated sample.
5. Compare the illustrative traces; discuss heat as a possible explanation, with missing evidence explicit.
6. Propose cooling and repeating with matched conditions. Export the rehearsal record.

Space / Right Arrow advances; Left Arrow goes back; F toggles fullscreen when focus is outside a form control. Buttons work with a mouse or touch. Back removes later markers; Reset asks before clearing. Reload restores the presentation position. Once the service worker has cached the site, it can reopen offline. The timer is informational and never triggers a transition.

Optional **Use live camera** requests the camera on the browser's device. On the Pi browser this can select its webcam if it is available to Chromium. A Vercel page on a laptop cannot magically access a webcam plugged into another computer. The physical station may already hold the Pi webcam; close that capture before expecting browser access. Denied access or disconnection restores the illustration without blocking the flow. Frames can be downloaded separately. Camera pixels are not used for the prepared explanation or trace.

## Evidence boundary

All narrative is prepared rehearsal content. The illustrated cups and traces are not measurements. No Gemini call is made or implied. Live camera is labeled preview only. Hot-water preparation is reported, and temperature remains unmeasured; air quality remains disconnected. No accuracy, confidence, calibrated temperature or gas concentration is invented. A real hot-water run may differ from the expected picture. If it does, describe what actually happened and use the illustration only as a scenario walkthrough.

The expected chemistry is qualitative: heat can weaken starch–iodine color, but a photo alone cannot diagnose a hidden cause. See the [AACT starch–iodine temperature experiment](https://teachchemistry.org/periodical/issues/march-2020/designing-a-greener-le-ch-telier-s-principle-lab) for the relevant heat/cool demonstration. A matched cool-and-repeat experiment is needed to investigate the proposed explanation.
