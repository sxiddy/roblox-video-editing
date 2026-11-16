# Roblox video editing: instructions for any agent (Fable, Opus, Sonnet)

This repo makes Roblox video edits and thumbnails for clients. It is for Roblox only. The owner shoots
clips when asked and edits them. The method is fixed and written down so that any model can follow
it step by step. Do not improvise a different workflow.

## Read in this order, before doing anything
1. `MASTER_PLAN.md`: the whole method. Section 2 is the job pipeline (stages A to F, each with a
   gate), section 4 the Roblox theme tables, section 8 thumbnails.
2. `LESSONS.md`: mistakes already made on earlier jobs. Do not repeat them.
3. `pipeline/TODO.md`: current state of the toolkit and known problems.
4. The job's own pages in `jobs/<job>/` (BRIEF.md, STYLE.md, REFERENCE.md, EDIT.md), if a job exists.

## Start of every session
```bash
python setup/check_setup.py
```
Every FAIL line prints its fix; the commands are in `setup/INSTALL.md`. Fix FAILs before any job
work. WARN lines are optional items.

## Starting a new job
```bash
python pipeline/new_job.py <job-name>
```
Then work through the stages in `MASTER_PLAN.md` section 2 in order. The table "The toolkit" in
section 1 lists which script serves which stage. Each script's first lines give its exact command.

## Hard rules
- One stage at a time. A stage ends in a gate; when the gate says "the user approves", stop and
  ask the user. Never skip a gate, never build before BRIEF.md is confirmed.
- Every job gets its own style. Nothing is carried over from another client. The look comes from
  that job's footage, brand files and client words (Stage A2), mapped to ONE theme row in section 4.
- Measure, do not guess. Loudness, cut times, shot lengths, colours and BPM come from the scripts.
  Report the numbers the scripts print; if a script fails, show the error and fix the cause.
- Two Pythons. System `python` for most scripts; the GPU env
  `"C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe"` for `analyze_music.py`, `depth.py`,
  `matte.py`, `mask_track.py`, `sfx_check.py`. GPU scripts print the device and stop if it is not the RTX 4050.
- Run scripts from this folder, as `python pipeline/<script>.py ...`. All paths are in
  `pipeline/config.py`; change paths there only.
- Never hard-code `h264_nvenc` (it does not work on this machine's driver). Use
  `config.fast_encoder()` for previews; masters are libx264 CRF 14.
- The cut is built only by `python pipeline/build_edit.py jobs/<job>/edit.json` (add `--preview`
  until the layout is locked). Never hand-write render code for the cut. Anything fancier
  (slow motion, cutout, depth, motion graphics, 3D) is made as its own clip first, then placed in
  the edit file. The script checks the edit rules, renders, masters the audio and runs QC.
- Music: only tracks whose licence allows monetised YouTube use. Record licence, credit line and
  source URL in the music JSON and in EDIT.md.
- Roblox character renders and animation belong to the other project,
  `C:/Users/Siddharth D/Projects/gfx and animation roblox blender` (read its CLAUDE.md). Request
  renders from it; do not rebuild its work here. Shooting Roblox footage ourselves is covered in
  `MASTER_PLAN.md` section 4, "Shooting Roblox ourselves".
- Media never goes into Git (`.gitignore` covers it). Job pages, scripts and notes do.
- One render at a time. Do not edit a script while a render that uses it is running.
- Before saying anything is done: run it and read the real output. Run `qc.py` on every delivery
  file; a delivery with a FAIL line is not finished.
- Never replace or delete a file in `deliver/` without the user's say-so.

## End of every session
- Add what went wrong and how it was fixed to `LESSONS.md`, the moment it happens.
- Update `pipeline/TODO.md` with what was done and what is left.
- Commit and push (`git add -A`, commit, `git push`) when the user has asked for it.
