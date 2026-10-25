# Litmus demo video

The animations and overlays for the demo, built with [Remotion](https://remotion.dev) in the same design language as the app. Sound effects are synthesized (`python make_sfx.py`), so there's nothing to license.

```bash
npm install
npm run studio                 # preview and scrub every composition
npx remotion render Main out/litmus-demo.mp4
```

## Adding the footage

1. Copy the clips into `public/footage/` (not committed).
2. In `src/Main.tsx`, fill in `FOOTAGE` with each clip's file name and the second it should start from, e.g. `tap: { file: "IMG_2041.MOV", from: 3.2 }`.
3. Line up the overlays with the footage. Name tag positions are the tops of your heads (0–1 of the frame), and detection boxes are `[x, y, width, height]`.
4. For music, drop a track in `public/` and render with `--props='{"music":"music.mp3"}'`.

## Compositions

| id | what |
|----|------|
| `Main` | The whole edit, with placeholders until footage is added |
| `Pipeline` | Gemini → structured data → Tiger Data (hypertables, hash chain, continuous aggregate, pgvector, hybrid search) |
| `TapStart`, `NameTags`, `SessionTitle`, `Detection`, `SpeechCommit`, `CommitLog`, `ColorChange`, `Sealed` | Overlays. Render with transparency for another editor: `npx remotion render NameTags out/tags.mov --codec=prores --prores-profile=4444` |
| `Opening`, `Brand`, `EndCard` | Title cards |
