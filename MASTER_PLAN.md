# MASTER PLAN: Roblox video edits and thumbnails

Written 2026-11-11. This is the standing plan for every edit and thumbnail from now on. It is written so
any agent (Opus included) can follow it without taste calls: every stage has inputs, exact numbers, and a
pass/fail gate. Read order for a new session: this file, then `LESSONS.md`, then the job's brief.

Scope: trailers, montages, showcases, announcements, shorts, for Roblox, with or without
supplied clips.
Roblox character renders and Roblox animation are owned by the other project
(`C:/Users/Siddharth D/Projects/gfx and animation roblox blender`, read its `CLAUDE.md`,
`gfx_mistake_log.md`, `docs/GFX_MASTER_PIPELINE.md`). This plan only says what to request from it.

---

## 0. What was wrong so far (diagnosis from all files)

Video (Tides V1 to V8.3, Critical analysis):
1. Direction flipped every version (slow, fast, slow, minimal, text back) because no brief was locked.
   Eight versions were built against plan files instead of the client's words.
2. Footage was the ceiling: 31 clips, 10 s each, mostly static wide shots with a tiny player, a third
   too dark. No edit fixes missing shot variety. Nobody recorded or requested more.
3. Rhythm was mechanical: cuts on a fixed bar grid (V5: six shots at exactly 4.5 s), not on motion.
4. Effects were pasted on (bubbles, rays, flares on shader footage), transitions were presets.
5. Type changed family every version (Garamond, Luckiest Guy, pixel, Cinzel, Lilita, Montserrat,
   Manrope). Fonts are what the client judges first.
6. Sound: synthesised SFX, no real library; flat loudness in several versions; V8.3 still peaks at
   -0.1 dBTP (measured today; target is -1.0).
7. V8.3 measured today: 54.75 s, only 5 detectable cuts, 8 toasts/pops on screen for long holds.
8. The pipeline ran on CPU. The laptop has an RTX 4050 (6 GB) that was never used; a brief even told
   reviewers "no CUDA GPU". Renders, matting, stems and interpolation were all slower than needed.

Thumbnails (Tides V3, Critical):
1. Character is hand-built boxes with a hand-painted skin, so it looks like a toy, not the player.
2. Background is a blurred, brightened 1080p video frame: smeared, low detail.
3. Character and background are lit separately, so it reads as a cutout.
4. Text plate ("OFFICIAL TRAILER" pill) looks like a web button; logo is a default pixel font.
5. Clip-art FX (uniform bubbles, droplets). Props float (furnace, crafting table, creeper in a row).
6. No depth: no foreground, no haze, no depth of field, no contact shadows.

---

## 1. Machine and tools (state on 2026-11-11)

Hardware: i7-13645HX, 16 GB RAM, RTX 4050 Laptop 6 GB, Windows 11. ffmpeg 9.0.2 full (has
h264/hevc/av1 NVENC, libplacebo, vidstab, lut3d, xfade). Blender 5.2 (Cycles OptiX works).

Installed today (verified unless marked):
| Tool | Where | Use |
|---|---|---|
| GPU Python env, torch 2.11.0+cu128, CUDA true | `C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe` | every ML step below |
| sam2, transformers, beat_this, demucs, rembg[gpu] in that env | same (install + weights: check `SETUP_STATUS` below) | masks, depth, beats, stems, matting |
| rife-ncnn-vulkan (GPU, tested) | `Projects/media-tools/rife-ncnn-vulkan/` | clean slow motion (model `rife-v4.6`) |
| realesrgan-ncnn-vulkan (GPU, tested) | `Projects/media-tools/realesrgan-ncnn-vulkan/` | upscale plates/punch-ins (`realesrgan-x4plus`) |
| scenedetect 0.7.3, auto-editor 29.3.1, pedalboard, pyloudnorm, moderngl | system Python 3.12 | cut detection, motion ranking, audio FX, loudness, GLSL transitions |

Already there before today: system Python (torch CPU, opencv, librosa, rembg, mediapipe, moviepy,
realesrgan, faster-whisper, playwright), HyperFrames, Remotion (`Projects/drive-reel-mcp`), yt-dlp,
repo library `Projects/github-repos` (source clones with REPO.md cards: gl-transitions, Natron,
ReplayMod, chunky, PySceneDetect, etc.), skills (hyperframes, media-use, blender-*, roblox-gfx-*).

SETUP_STATUS (finish these first in the next session):
- [x] `media-gpu` imports `sam2, beat_this, rembg, transformers, demucs`; torch sees the RTX 4050.
- [x] Weights cached: `facebook/sam2.1-hiera-small`, Depth-Anything-V2 Small+Base (hf),
      beat_this `final0`, rembg `birefnet-general` + `isnet-general-use`, demucs `htdemucs` +
      `htdemucs_ft`.
- [x] Matting runs on the GPU through torch: `pipeline/matte.py` loads `ZhengPeng7/BiRefNet`
      (weights cached 2026-11-16, 1.6 GB VRAM). Do NOT use rembg for matting: its onnxruntime-gpu
      1.31 wants CUDA 13 DLLs, torch ships CUDA 12.8, so rembg silently runs on the CPU.
- [x] Smoke-tested on the V8.3 trailer on 2026-11-16, all on the GPU: sam2 video masks
      (`mask_track.py`), Depth-Anything (`depth.py`), beat_this (`analyze_music.py`), RIFE
      (`slowmo.py`). Real-ESRGAN was tested on a trailer frame on 2026-11-11.
- [ ] NVENC does not work: ffmpeg 9.0.2 needs NVIDIA driver 610 or newer, the laptop has 581.86.
      Until the user updates the driver, `config.fast_encoder()` falls back to Intel Quick Sync or
      libx264. Never hard-code `h264_nvenc`; call `fast_encoder()`.
- [x] SFX library: 115 sounds in `Projects/media-library/sfx/` (index `sfx.json`), -18 LUFS copies
      in `Projects/media-library/sfx_norm/` (use these). Not yet weeded by ear: `sfx_norm/report.json`
      flags the ones to check.
- [x] Repo is on GitHub (`origin`, branch `main`).
- [ ] Previews: use `config.fast_encoder()` (see the NVENC item above); masters stay libx264 CRF 14.

### The toolkit (`pipeline/`, every script tested on real media on 2026-11-16)
Run `python setup/check_setup.py` first in any new session: it prints PASS/FAIL for every tool.
"sys" = system `python`; "gpu" = `C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe`.
Each script's first lines show its exact command. All paths live in `pipeline/config.py`.
| Stage | Script | Python | What it gives |
|---|---|---|---|
| A | `new_job.py <name>` | sys | `jobs/<name>/` with BRIEF, STYLE, REFERENCE, EDIT pages and folders |
| A2 | `palette.py` | sys | 5 dominant colours, brightness, saturation, look guess |
| B | `audit_footage.py` | sys | `footage.json` + contact sheets: cuts, motion, luma, flags, best windows |
| B | `record_screen.py` | sys | our own shots by screen capture, video only (Roblox, Studio, or Minecraft without Flashback) |
| C, F | `qc.py [--measure-only]` | sys | reference numbers, or the Stage F pass/fail gate |
| D | `analyze_music.py` | gpu | BPM, beats, drops, song window, score out of 6 |
| E | `build_edit.py jobs/<job>/edit.json` | sys | THE BUILD: cuts, speed, transitions, grade, text, music + SFX mix, master, QC, from the edit file |
| E | `slowmo.py` | sys | RIFE slow motion of a clip range |
| E | `depth.py` | gpu | depth map (image or video) |
| E | `matte.py` | gpu | cutout of the most salient subject (BiRefNet) |
| E | `mask_track.py` | gpu | matte + per-frame box of ONE chosen object (SAM2) |
| E | `sfx_fetch.py`, `sfx_normalize.py` | sys | CC0 SFX library and its -18 LUFS copies |
| E | `sfx_check.py` | gpu | flags SFX that do not match their category or start late (`sfx_norm/check.json`) |
| E | `master_audio.py` | sys | -14 LUFS, true peak <= -1.0 dBTP, measured on the encoded file |
| T5 | `thumb_check.py` | sys | small-size, greyscale, blur sheet and reference grid |

Known limits seen in testing: `matte.py` also selects on-screen UI (an advancement popup), so
record with the HUD off or use `mask_track.py`; `mask_track.py` drifts to another object once the
subject leaves the frame, so end the range before that.

GPU rule: any step using torch, onnx, RIFE, ESRGAN or Cycles must run on the GPU. Print the device at
the start of each script and stop if it says CPU.

---

## 2. The job pipeline (same for every edit)

Each stage ends in a gate. Do not start the next stage until the gate passes.

### Stage A. Brief lock (no building before this)
Fill `jobs/<job>/BRIEF.md` with: game, edit type, theme (section 4), length, aspect (16:9, 9:16, both),
deadline, must-show features, must-keep moments, banned things, facts that must appear (IP, date,
links), 2 to 3 reference videos the client likes and 1 they dislike, who approves.
Paste the client's raw words, never a summary. If two notes conflict, ask one short question.
Always ask the client, in the first message: (1) can we join the server or get a world download for
extra shots and the thumbnail, (2) the main player's username(s) for skins/avatars, (3) any logo or
brand files. If the answer is no or nothing comes back in time, continue on the no-access route and
note it in the brief.
Default format: 16:9, 1920x1080 or higher, 60 fps, for YouTube. Vertical cuts only if the brief asks.
Gate: the user confirms the brief in chat.

### Stage A2. Style analysis (per job, nothing carried over from other clients)
The agent (Opus or Sonnet is fine) works out the look from evidence, in this order:
1. Collect: the supplied clips (contact sheets), the server/game's own material (logo, Discord
   banner, website, store page, in-game hub, existing videos, Roblox game icon and thumbnails), the
   client's words about vibe, and the references from the brief.
2. Extract facts, not opinions:
   - palette: 5 dominant colours from the footage and from the brand material (k-means on frames);
   - brightness and saturation level of the footage (bright cartoon, natural, dark moody);
   - what the server/game is about: mode, audience age, tone words the client used;
   - energy the footage can support (motion score from Stage B) and the references' pace.
3. Map to ONE theme row in section 4 (plus at most one contrast theme). If two rows fit equally,
   show the user both with a one-line difference and let them pick.
4. Write `jobs/<job>/STYLE.md`, every line a decision:
   - theme row chosen and why (two sentences, citing the evidence);
   - palette: background, primary, accent, text colour (hex), taken from step 2;
   - type: one brand face + optional display face, chosen to match the server's own logo/brand
     if it has one, otherwise from the theme row; show 3 candidates rendered on a real frame and
     pick by legibility at 25% scale;
   - pace targets (median shot length per section), transition set (which of the allowed list),
     grade approach, sound palette, music genre and BPM range;
   - the same choices for the thumbnail: subject, mood, colours, lettering style;
   - a "not this" list from the client's dislikes.
5. One style frame: a single finished still (real frame + type + grade) and one thumbnail sketch.
Gate: the user approves STYLE.md and the style frame. After that the style is locked for the job;
changing it needs the user's say-so, not a reviewer's.

### Stage B. Footage audit, then fill the gaps
1. Catalogue every clip: `scenedetect` for internal cuts, per-second motion score (mean optical-flow
   magnitude), mean luma, sharpness (Laplacian variance), subject size (SAM2/BiRefNet mask area %).
   Write `footage.json` and a contact sheet per clip.
2. Tag each usable moment with one of: establishing, hero action, detail/close-up, feature proof,
   character, transition-capable (whip, pass-through, dive, door), ending.
3. Coverage check against the theme's shot list (section 4). A trailer needs at least: 2 establishing,
   3 hero actions, 3 close/detail, 1 proof per feature, 1 ending plate. Mark what is missing.
4. Fill gaps, in this order:
   a. ask the client for specific shots (send a written shot list: subject, camera move, seconds);
   c. Roblox: request renders/animations from the Roblox project, or record in Studio/in-game with
      the free camera (Shift+P), graphics 10, UI hidden;
   d. Blender shot (logo sting, character hero shot, map fly-through).
Gate: coverage table has no empty row, or the user accepted the gap in writing.

### Stage C. Reference study (short, measured)
For the 2 to 3 client references only: cut times (scdet), shot length curve, loudness curve
(ebur128 momentary), BPM, where the logo appears, text sizes as % of frame height, transition count by
type. One page: `REFERENCE.md`. The edit must match or beat each number.
Gate: page written; numbers become the targets in Stage D.

### Stage D. Music first, then the paper edit
1. Pick music (section 6). Run `beat_this` for beats and downbeats, librosa for sections and onset
   strength, ebur128 for the energy curve. Mark: intro, build, drop(s), breakdown, outro, final hit.
2. Choose the song window so its biggest drop lands on the hero moment and its last hit lands on the
   end card. Edit the song (cut on downbeats, 20 to 40 ms crossfades) rather than bending the picture.
3. Write `EDIT.md`: a table with one row per shot: time in/out, clip + source in/out, why this shot,
   cut type, what motion carries across the cut, speed, text, SFX. Every decision made, nothing "TBD".
4. Rhythm rules:
   - Shot length follows energy: intro 2 to 4 s, build shortens each bar, drop 0.4 to 1.2 s, breathe
     after the drop, ending holds 4 to 6 s.
   - Never three shots in a row with the same length. Never cut every shot on the downbeat: roughly
     60% on beats, 25% on the action inside the shot (impact, turn, splash), 15% a few frames early
     (cutting 2 to 3 frames before the beat feels tighter than exactly on it).
   - Each clip once. A cut must change at least two of: subject, scale, angle, colour, motion direction.
   - Keep hero actions whole; transitions go around them.
5. One review pass by a fresh agent given the brief, references and LESSONS (max 2 rounds).
Gate: the user approves `EDIT.md` plus a 10 to 15 s rough cut of the strongest section with final
music. Never show a plan with open questions.

### Stage E. Build
Copy the approved EDIT.md shot table into `jobs/<job>/edit.json` (one entry per row) and build with
`python pipeline/build_edit.py jobs/<job>/edit.json --preview`, then without `--preview` for
delivery. Do not hand-write ffmpeg or HyperFrames code for the cut itself. Shots that need more
than the edit file offers (slow motion, cutouts, depth effects, motion graphics, 3D) are made first
as their own clip with the other scripts, HyperFrames or Blender, saved into `clips/`, and then
used in the edit file like any other clip. Text and SFX times come from `<out>.timeline.json`.
Order: conform cuts, speed work, stabilise/reframe, transitions, grade, text/graphics, sound, master.
Preview renders at 960x540 NVENC; full quality only after layout is locked. Never edit scripts while a
render runs. One render at a time.

### Stage F. QC gate (all must pass, measured on the encoded file)
- [ ] Frame 0 is bright and interesting; hook lands within 2 s; logo by the reference's time.
- [ ] No clip repeats (scenedetect + perceptual hash of shot middles).
- [ ] No black frames except intended (blackdetect); ends on the end card with the last music hit.
- [ ] Shot lengths: no three equal in a row; histogram is not a single spike.
- [ ] Every text frame checked: not on a face/subject, inside title-safe (5% margins), readable at
      25% scale (phone), one sans family + at most one display face.
- [ ] Audio: -14 LUFS integrated (+/-0.5), true peak <= -1.0 dBTP, LRA >= 7, no clipping, music
      credit present if the licence needs it.
- [ ] Side by side with each reference at the same timestamp: ours is not worse on image, rhythm, type.
- [ ] Full watch at 1x with sound, once on a phone-sized window.
- [ ] Deliver master + preview with ONE large drifting semi-transparent mark. Files into Downloads for
      the user to upload.
Then log lessons in `LESSONS.md` the moment they happen.

---

## 3. Craft rules (how each part gets better)

### Cutting
- Cut on motion: leave shot A at its motion peak, enter shot B already moving the same way.
- Match cuts: same shape/position (sun to torch, horizon to horizon), same action (jump to dive).
- J and L cuts: the sound of the next shot starts 4 to 10 frames early; this alone removes the
  "slideshow" feel.
- In-points: never on a still frame. Trim until something is already happening.
- Punch-ins are hard crops (cut to 115 to 130%), upscaled with Real-ESRGAN if over 120%.

### Speed
- Ramps only on a real action (swing, jump, dive, reveal): 100% to 250% in, drop to 40 to 50% on the
  impact, back out. Ease with a curve, never a step. Use RIFE (`rife-v4.6`) to make slow motion from
  60 fps footage; frame duplication only for pixel-art UI.
- Motion blur on fast sections: ffmpeg `tmix` over RIFE-interpolated frames (render 240 fps, average
  4), not on slow shots.

### Camera fixes
- Stabilise shaky handheld with vidstab (smoothing 10 to 15), then crop 4 to 6%.
- Add slow push (1.00 to 1.04) only to locked-off shots; never to shots that already move.
- 9:16 versions: track the subject with SAM2 and reframe per shot, do not centre-crop.

### Transitions (default is a cut)
Allowed, each used at most twice per video, each needing a reason from the footage:
1. Hard cut (70 to 85% of all edits).
2. Whip/pan blur: only when both shots pan the same direction. Directional blur 6 to 8 frames.
3. Pass-through/object wipe: a block, tree, character or wall crosses frame; mask it (SAM2) and
   reveal the next shot behind it.
4. Match dissolve 8 to 12 frames for time passing or the ending.
5. Light/flash hit: 2 to 3 frames to white or the scene's key colour on a drop; max 2 per video.
6. Zoom-through: push into a dark or bright area (door, portal, sun) and out of the next shot's.
7. Diegetic: water surface, portal, death screen, teleport, door, elevator, loading screen, UI open.
8. Speed-ramp cut: end of A accelerates, start of B decelerates.
9. Glitch/RGB split/shake: only for PvP, horror, tech themes; 3 to 5 frames.
GLSL transitions from `gl-transitions` (via moderngl) are allowed only as the engine for items 2, 6, 9.
Banned unless the client asks: star wipes, page curls, cube spins, kaleidoscope, light-leak packs,
ripple on dry land, any transition on every cut.
Every non-cut transition gets a matched sound (section 7).

### Colour
- Shader footage that already looks graded: leave it. Only match shots to each other (exposure,
  white balance) so neighbours agree.
- Vanilla or flat footage (most Roblox, non-shader Minecraft): one look for the whole video. Order:
  exposure/white balance per shot, contrast curve, saturation 1.05 to 1.20, a gentle LUT at 30 to 50%,
  then optional halation/bloom at <= 8% and fine grain. Skin and UI colours must stay true.
- Dark shots: lift with a curve on the GPU-denoised frame (nlmeans or hqdn3d first), never plain
  brightness. If it still looks muddy, drop the shot.
- Check on a scopes sheet: no clipped highlights over 2% of the frame, blacks not above 6 IRE.

### Text and graphics
- One brand face per job, decided in STYLE.md (Stage A2) and kept for the whole job (logo, captions,
  end card). It is chosen fresh for each server/game; nothing is reused across clients by default. One optional display face. In-game UI fonts only inside recreated game UI.
- Sizes as % of frame height: logo 9 to 15, headline 5 to 7, caption 3 to 4.5, sub 2.2 to 2.8,
  IP/links 3 to 4.5. Nothing under 2.2.
- Each caption says something specific to this server/game (a real feature, number or name). No
  generic slogans. Maximum words on screen: 5.
- Motion: in 4 to 8 frames (opacity + 8 to 14 px rise or tracking settle), hold at least
  0.25 s + 0.06 s per character, out with the cut or a 4 to 6 frame fade. Vary position per caption.
- Integrate at least one text into the scene per video: behind the subject (SAM2/BiRefNet mask),
  tracked to a surface (OpenCV feature tracking), or occluded by terrain (depth from
  Depth-Anything-V2). Never over a face.
- Game UI as graphics is the strongest device: Minecraft advancement toast, chat line, tab list,
  multiplayer screen, scoreboard; Roblox badge award, leaderboard, chat bubble, proximity prompt,
  kill feed. Max 3 per video, 2 to 2.5 s each, with the real UI sound.
- End card: logo + one call to action + IP/link, on a clean plate, held 4 to 6 s, readable on a phone.
- Tools: HyperFrames for typography layers (alpha render), compositor for placement. Verify every
  effect in a real render, not a snapshot.

### Things that read as AI-made (never do)
Even shot lengths; every cut on the downbeat; the same caption animation every time; centred wide
tracked caps with a tiny subline on every shot; glow + light sweep titles; dark scrims behind text;
stock overlays on footage; transitions on every cut; generic slogans; fake UI that says nothing real;
four font families; a title that just sits there; no ambient sound; a fade to black with no hit.

---

## 4. Theme playbooks

For each theme: pace, music, transitions, type, colour, sound, shots that must exist. Pick ONE theme
per video; a second only as a contrast section.

### Roblox
Roblox footage is flat and UI-heavy, so the edit carries more: hide UI when recording (or crop it),
grade every shot, and lean on rendered characters from the Roblox project for hero shots.
| Theme | Pace | Music | Transitions | Type | Colour | Signature sound | Must-have shots |
|---|---|---|---|---|---|---|---|
| Game trailer (sim, tycoon, RPG) | 0.8 to 1.6 s | upbeat electronic / future bass | cuts on beat, zoom-through, UI pops | rounded heavy sans, stroke allowed (Roblox look) | bright, saturated, clean whites | UI clicks, coins, level-up | core loop in 3 shots, progression before/after, pets/items, world, logo + "Play now" |
| Obby / parkour | 0.5 to 1.2 s | high-energy pop, DnB | speed ramps on jumps, whips | bold italic | vivid | jumps, wind, checkpoints | hardest jump, fail then success, speed section, finish |
| Fighting / anime (Blox Fruits style) | 0.3 to 0.9 s on drops | phonk, J-rock, trap | impact frames, shake, flash, smear, RGB | heavy italic, name cards | saturated, strong rim, dark backgrounds | hits, ability sounds, bass | ability showcase per character, clash, ultimate, boss |
| Horror (Doors style) | slow then bursts | drones, stingers, silence | cut to black, flicker, glitch | small plain caps | dark, desaturated, grain | ambience, footsteps, stingers | corridor, entity glimpse, chase, door |
| Roleplay / life / hangout / fashion | 1.5 to 3 s | pop, R&B, lo-fi | cuts, soft dissolves, pass-throughs | clean modern sans or soft serif | warm, soft bloom, pastel | city ambience, UI | avatars close-up (rendered), locations, outfits, friends |
| Shooter / combat | 0.4 to 1.0 s | trap, dubstep, rock | whips, shake, muzzle-flash cuts, kill-feed | condensed bold, kill-feed UI | contrasty, slightly cool | gunfire, hitmarkers, reloads | multi-kill, clutch, weapon inspect, map wide |
| Montage / edit of a player or group (velocity edit) | follows the song, 0.2 to 1 s | the client's song; sync to lyrics and drums | velocity ramps, shake, flashes, 3D turns | minimal, lyric words only | strong grade, glow at <= 10% | song only + a few hits | character renders (from the Roblox project), poses, slow-mo peaks |
| Update / event / code announcement | 0.8 to 1.5 s | energetic | cuts, flash, countdown | big bold, code or date huge | brand colours | risers, impacts | 3 new things, date, code on screen 3 s+ |
| General Roblox edit, not about one game (avatar or outfit edit, friend-group edit, meme, intro/outro, channel trailer) | follows the song or the joke, 0.3 to 2 s | the client's pick, or by mood | cuts, velocity ramps, one signature move | from the person's or channel's own branding | from the avatar's colours | song + a few hits | the avatar(s) rendered large, 3+ poses or outfits, one payoff moment, name or handle on screen |

Every Roblox experience is different, so these rows are starting points, never a finished style.
For each job: play or watch the experience first and write in BRIEF.md what kind it is, what its
own UI, colours, fonts and sounds are, and what players actually do in it. Stage A2 then builds
that job's STYLE.md from this evidence and picks the closest row; if no row fits, combine two and
say so in STYLE.md. If the job is not about a game at all, write "none: general edit" as the
experience in BRIEF.md, use the last row, and take the style from the person, group or channel the
edit is for. Avatars, GFX renders and animations always come from the Roblox GFX project.

### Shorts / TikTok (both games)
| Theme | Pace | Music | Transitions | Type | Colour | Signature sound | Must-have shots |
|---|---|---|---|---|---|---|---|
| Shorts / TikTok (both games) | hook in 1 s, 0.5 to 1.2 s cuts | trending or high-energy, loopable | cuts, 1 signature | captions 4.5 to 6% height in the middle third | punchy | hits on every caption | 9:16, 15 to 35 s, first frame is the payoff, last frame loops into the first |

When no clips are supplied:
- Roblox: request character renders/animations from the Roblox project (give it: usernames, pose or
  action list, camera angle, duration, fps, transparent background yes/no, lighting mood); record
  environments in-game with the free camera; build motion-graphics sections in HyperFrames.

### Shooting Roblox ourselves (the user is often asked to shoot AND edit)
Write the shot list first (from the theme row's must-have shots: subject, camera move, seconds),
then shoot it; never "record some gameplay and see".
1. Access, asked in the brief: edit access to the place (best: open it in Studio), or a private
   server plus admin/cinematic-camera commands, or nothing (plain gameplay only). The free camera
   (Shift+P) only works where the account has developer access, and always in Studio.
2. Settings before every session: fullscreen at native resolution; Settings > Graphics Mode
   Manual, quality 10; frame-rate cap at 60 or higher; chat, leaderboard and backpack closed.
3. UI: Roblox has no universal hide-UI key. In Studio, disable the game's ScreenGuis and the core
   UI (`StarterGui:SetCoreGuiEnabled(Enum.CoreGuiType.All, false)`) for clean plates. In a live game
   ask the developer for a hide-UI option; otherwise frame so the UI can be cropped (shoot wider,
   subject inside the centre 80%) or keep the UI on purpose for "feature proof" shots.
4. Record with `python pipeline/record_screen.py --out jobs/<job>/clips/<shot>.mp4`. Never use
   Roblox's built-in recorder (low bitrate). One file per shot, named after the shot list row.
5. Camera: slow, eased moves only (hold a direction, do not jitter the mouse); 6 to 10 s per take
   with 1 s of handle at each end; three takes of every hero shot; move the camera through or
   past something for transition-capable shots.
6. Shoot more than the edit needs: 2 establishing, 3 hero, 3 detail, 1 proof per feature, 1 ending
   plate at minimum (Stage B coverage), plus avatar close-ups to hand to the Roblox project.
7. Run `audit_footage.py` on the takes the same day; reshoot anything flagged dark, static or soft
   while the session is still open.

---

## 5. Edit types (structure templates)

| Type | Length | Structure |
|---|---|---|
| Server/game trailer | 35 to 60 s | hook 0 to 3 s, logo by 3 to 8 s, 3 to 5 feature beats, build, drop montage, breathe, end card 4 to 6 s |
| Teaser | 12 to 20 s | mystery image, 3 fast glimpses, logo + date |
| Update/event announcement | 20 to 40 s | "what's new" hook, 3 proofs, date/how |
| Montage / highlights | 45 to 120 s | best clip second (not first), sync to song sections, best clip last |
| Showcase / cinematic | 60 to 150 s | slow open, tour by area, peak at the best build, quiet close |
| Player/group edit | 15 to 45 s | lyric and drum sync, renders + effects, loopable end |
| Short | 15 to 35 s | payoff first, one idea, loop |
All of these are delivered 16:9 for YouTube by default. A 9:16 cut is made only when the brief asks
for it, from the same EDIT.md with subject-tracked reframing.

---

## 6. Music selection (method, not taste)

1. From the brief take: theme, energy (1 to 5), references' BPM and genre.
2. Gather 8 to 12 candidates. Hard rule: the video must not get a copyright strike or claim, and
   nothing is paid. Allowed sources, in order:
   - YouTube Audio Library (safest: made for YouTube, no claims; some tracks need a credit line);
   - Pixabay Music (free, no credit needed; check the track page for a Content ID note and skip
     any track that has one);
   - NCS (free on YouTube with the exact credit text from the track page);
   - Uppbeat free tier (needs the per-download credit code in the description, or it gets claimed);
   - Free Music Archive / incompetech, CC BY or CC0 only (credit required for CC BY);
   - HeyGen catalogue via `media-use` if signed in.
   Never: chart or game-soundtrack songs, "no copyright" re-uploads from random channels, tracks
   marked CC BY-NC or CC BY-ND, anything whose licence page cannot be opened and saved.
   For each candidate save in `music.json`: title, artist, source URL, licence, the exact credit
   line, and the date checked. The credit line goes in the YouTube description (and on the end card
   only if the licence demands it on screen).
   Exception: if the client insists on a specific commercial song, the user must confirm in chat
   that the client accepts the claim risk; otherwise offer the closest safe track instead.
3. Score each automatically: BPM in the theme's range; has a clear drop (momentary loudness jump
   >= 6 LU); has a quieter intro or breakdown (>= 8 LU below the drop); section lengths fit the target
   runtime; a clean final hit or a tail that can be cut on a downbeat; LRA >= 8.
4. Keep the top 3. Render the same 15 s of the edit under each. The user/client picks by ear.
5. Mix from the original file. Stems (demucs `htdemucs_ft` on GPU) only to duck drums or bass for a
   section, never to rebuild the song. Compare the <90 Hz band to the source before delivery.
6. Master: static gain to -14 LUFS, limiter ceiling 0.78 (about -2 dB) so AAC lands <= -1.0 dBTP,
   never one-pass loudnorm. Measure the encoded file.

---

## 7. Sound design

Build a real library once: `C:/Users/Siddharth D/Projects/media-library/sfx/` with folders
`whoosh, impact, riser, sub_drop, ui, water, fire, wind, footsteps, ambience, minecraft, roblox`.
Sources: Openverse/Freesound CC0 via `npx hyperframes media-use resolve --type sfx`, Kenney audio
packs (CC0), Sonniss GDC bundles (royalty-free), Pixabay SFX. Minecraft sounds can be read from the
local install (`.minecraft/assets/indexes/*.json` maps names to hashed files in `assets/objects`);
Roblox UI sounds likewise from the client's own game. These are game assets: fine inside videos about
that game, do not redistribute the files (keep them out of the Git repo).
Normalise every SFX to -18 LUFS, trim silence, name by content. Keep a `sfx.json` index with licence.

Layers on every edit, mixed under the music:
1. Ambience bed per scene (-28 to -22 LUFS), crossfaded at cuts, starting 4 to 10 frames early.
2. Diegetic spot sounds for visible actions (splash, hit, door, footsteps), -20 to -14.
3. Transition sounds matched to the picture: whoosh length = transition length, pitch falls on exits.
4. Musical accents: riser 1 to 2 bars before a drop, sub drop + impact on it, reverse cymbal into
   title cards. At most one per section.
5. UI sounds for every game-UI graphic.
Mix moves: 3 to 6 dB music dip for 0.3 to 0.5 s before a drop; low-pass sweep for underwater/indoor;
sidechain the bed 2 to 3 dB under impacts. No sound may be synthesised if a recorded one exists.

---

## 8. Thumbnails (every thumbnail from now on)

Goal: looks like a paid artist's render, reads in one glance at 168x94 px.

The thumbnail's mood, colours and lettering come from the job's STYLE.md (Stage A2), not from the
last thumbnail made. If the client gave no world access, use route (b) or (c) in T2 for the
background and say so when showing it.

### T1. Concept first (one sentence, approved before building)
One subject, one emotion, one idea. Write: who is the subject, what are they doing, what is the
conflict or promise, where does the eye go first, second, third. Study the top 10 thumbnails by views
for the same game + theme (yt-dlp search, sort by views, 1M+; plus the client's pick) and note layout,
subject size, text words, colours. Sketch 3 layouts as grey boxes; the user picks one.

### T2. Real assets, never hand-built stand-ins
Roblox:
- Character renders come from the Roblox project (real avatar by username, its pipeline). Request:
  pose, camera, lighting direction, 4K, transparent + shadow pass. The background is a real in-game
  screenshot or a Blender set that project builds.

### T3. Render rules (Blender, Cycles on OptiX)
- Camera 50 to 85 mm, f/1.8 to f/2.8 depth of field focused on the eyes; subject fills 45 to 65% of
  frame height, slight low angle, never centred flat-on. Rule of thirds.
- Pose with weight: bent knees/elbows, twisted torso, head tilted, hands doing something. Expression
  through the rig's face controls. Check the silhouette as a black shape: it must read alone.
- Light: one key matched to the plate's sun (direction and colour), strong rim/back light in a
  contrasting colour, low fill, HDRI for reflections. Contact shadows always. Volumetric haze between
  subject and background.
- Depth layers: blurred foreground element, sharp subject, softer background, atmosphere.
- Render 3840x2160, 256+ samples, denoise, with passes: combined, shadow, emission, mist/depth,
  cryptomatte. Tests at 50% / 32 samples until the layout is locked. Colour management: Standard or
  AgX chosen per image by checking the reds; never ship washed colours.

### T4. Post (the "Photoshop" stage, done in Python/compositor)
1. Composite passes; match black level and colour temperature of subject to plate.
2. Dodge and burn: brighten face and focal area, darken corners (vignette 10 to 20%).
3. Rim glow from emission pass, bloom <= 10%, light wrap from the background onto subject edges.
4. Colour: 2 to 3 dominant colours, subject colour complementary to the background; saturation up to
   +20%, local contrast (unsharp radius 40 px at 15%), final sharpen for the downscale.
5. FX only if they come from the scene (embers from a fire, spray from water, dust, god rays from a
   real light). No stamped bubbles, sparkles or arrows unless the reference style calls for them.
6. Text: 0 to 4 words total, at most 2 text elements. Custom lettering: thick weight, slight
   perspective or 3D (Blender text with bevel, lit by the same lights), outline + soft shadow,
   colour pulled from the scene. No pill buttons, no UI-style plates. Never cover faces, hands or
   held items; keep 40 px margins.
7. Export 3840x2160 master, 1920x1080, 1280x720 (JPEG under 2 MB for YouTube).

### T5. Thumbnail gate (all must pass)
- [ ] At 168x94 and 320x180: subject, emotion and text readable in one second.
- [ ] Greyscale check: subject separates from background by brightness alone.
- [ ] Squint/blur test (Gaussian 12 px): one clear focal point.
- [ ] Placed in a grid with the 8 reference thumbnails: ours is not the weakest.
- [ ] No cutout edge, halo, floating prop, mismatched shadow direction or soft background mush.
- [ ] Real skin/avatar confirmed against the player's in-game look.
- [ ] No AI tells: plastic gradients, symmetrical layout, button-like text plates, uniform particles.
- [ ] Fresh-agent review against the references (max 2 rounds), then show the user with ONE centred
      watermark.
AI image generation is not used for the hero or text. If ever used for a background element, it is
painted over/graded so no generated texture is visible, and the user is told.

---

## 9. Repo and backup

- Private GitHub repo holds: this plan, `LESSONS.md`, old plans/briefs/reviews, scripts
  (`tides-trailer/*.py`, `thumb/*.py`), `analysis/research/*.md|json`, and a `setup/` folder with the
  install commands from section 1. Media (video, audio, images, fonts, game assets) stays out
  (`.gitignore`); it lives on disk/Drive.
- After every job: commit the brief, EDIT.md, lessons, and scripts.

## 10. Decisions from the user (2026-11-11)
1. Shader mods: approved and installed (section 1).
2. Server/world access: clients give it sometimes, only if asked. So always ask in Stage A, and
   always have the no-access route ready (Stage B step 4).
3. Music: the only hard rule is no copyright strikes or claims. Free sources only; every track needs
   a licence that allows monetised YouTube use (section 6).
4. Format: 16:9 for YouTube is the default and the only deliverable unless the brief asks for more.
5. Style: nothing is fixed across clients. Each job gets its own look, derived from the server/game
   and the video's theme by the style analysis in Stage A2.
