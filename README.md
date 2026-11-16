# Roblox video editing

Everything needed to shoot, edit and deliver Roblox videos and thumbnails for clients: the full
method, the rules, the page templates for each job, and the scripts. It is written so that any
agent (Claude Fable, Opus or Sonnet) can follow it step by step with no taste calls: every stage
has exact numbers and a pass/fail gate. Minecraft has its own separate repo.

## Start here
1. `CLAUDE.md`: the rules every session follows, and the read order.
2. `MASTER_PLAN.md`: the whole method.
3. `LESSONS.md`: mistakes already made, so they are not repeated.
4. `pipeline/TODO.md`: what is tested and what is still open.

## Run a job
```bash
python setup/check_setup.py
```
```bash
python pipeline/new_job.py <job-name>
```
Then follow `MASTER_PLAN.md` section 2, one stage at a time. The user approves at every gate.

| Stage | What happens | Page or script |
|---|---|---|
| A. Brief | client's words, length, deadline, access | `jobs/<job>/BRIEF.md` |
| A2. Style | this job's own look: palette, fonts, pace, theme row | `STYLE.md`, `palette.py` |
| B. Footage | catalogue the clips, find gaps, shoot what is missing | `audit_footage.py`, section 4 "Shooting Roblox ourselves" |
| C. References | measure the 2 to 3 videos the client likes | `REFERENCE.md`, `qc.py --measure-only` |
| D. Music and paper edit | pick the song, write every shot | `analyze_music.py`, `EDIT.md` |
| E. Build | render the cut from the edit file | `edit.json`, `build_edit.py` |
| F. QC | pass/fail on the finished file | `qc.py` |
| Thumbnail | concept, real assets, render, checks | section 8, `thumb_check.py` |

## Where each part of the plan is (`MASTER_PLAN.md`)
| Section | What it covers |
|---|---|
| 0 | What went wrong on earlier work |
| 1 | The machine, installed tools, setup status, the toolkit table |
| 2 | The job pipeline: stages A to F with their gates |
| 3 | Craft rules: cutting, speed, camera fixes, transitions, colour, text and graphics, AI tells |
| 4 | Theme playbooks for Roblox (pace, music, transitions, type, colour, sound, must-have shots), Shorts, and "Shooting Roblox ourselves" |
| 5 | Edit types: trailer, teaser, announcement, montage, showcase, player edit, short |
| 6 | Music: allowed sources, licence rules, automatic scoring, mastering |
| 7 | Sound design: the SFX library, the five layers, mix moves |
| 8 | Thumbnails: concept, real assets, render rules, post, the gate |
| 9, 10 | Repo rules and the user's standing decisions |

## Files
- `pipeline/`: the scripts (below), `templates/` for the job pages, `config.py` for every path.
- `setup/`: `INSTALL.md` (how to rebuild the tools) and `check_setup.py` (PASS/FAIL per tool).
- `jobs/<job>/`: one folder per client job. Pages are committed; media stays out of Git.

## Scripts
Each script's first lines give its exact command.
| Script | What it does |
|---|---|
| `analyze_music.py` | Stage D: measure a song and score it against the plan's music rules. Run with the GPU env: |
| `audit_footage.py` | Stage B: catalogue every clip. |
| `build_edit.py` | Stage E: build the video from the edit file. Same file in, same video out, for any game. |
| `depth.py` | Section 3: depth maps with Depth-Anything-V2 (text behind objects, parallax, depth fog/blur). |
| `mask_track.py` | Section 3: follow one chosen object through a shot with SAM2 (object wipes, text behind a |
| `master_audio.py` | Section 7 step 6: master the final mix. Static gain to -14 LUFS, limiter ceiling 0.78, then |
| `matte.py` | Cut the main subject out of its background with BiRefNet (torch, GPU). Run with the GPU env: |
| `new_job.py` | Stage A: start a job folder with the four pages every job needs. |
| `palette.py` | Stage A2 step 2: palette facts from footage or brand material. |
| `qc.py` | Stage F: QC gate on the encoded file (also Stage C: measure a reference with --measure-only). |
| `record_screen.py` | Stage B step 4: record the screen for our own Roblox (or any game) shots. |
| `sfx_check.py` | Screen the normalised SFX library by machine, so only the doubtful sounds need a human ear. |
| `sfx_fetch.py` | Build the SFX library from Openverse (CC0 only) into Projects/media-library/sfx/<category>/. |
| `sfx_normalize.py` | Loudness-normalise the SFX library into a sibling folder; the originals are not touched. |
| `slowmo.py` | Section 3: clean slow motion with RIFE (GPU, Vulkan). Makes real in-between frames. |
| `thumb_check.py` | Section 8 T5: build the thumbnail gate sheets. The judging is done by eye, this only makes the views. |

## How this repo is made
It is generated from the private source repo `video-editing-pipeline` by
`tools/make_game_repos.py`. Job folders are created and edited here. Changes to the method, the
scripts or the templates are made in the source repo and regenerated, so both game repos stay in step.
