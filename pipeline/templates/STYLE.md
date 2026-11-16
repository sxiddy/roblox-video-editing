# Style: {job}

Created {date}. Stage A2 of MASTER_PLAN.md section 2. Every line is a decision backed by evidence
from THIS job (its clips, its brand material, the client's words). Nothing carried over from other
clients. After the user approves, the style is locked; only the user can change it.

## Evidence (facts, not opinions)
- Footage palette (`python pipeline/palette.py <clips> --out jobs/{job}/style/footage`):
- Brand palette (`python pipeline/palette.py <logo, banner...> --out jobs/{job}/style/brand`):
- Footage brightness / saturation / look guess:
- What the server or game is about (mode, audience age, client's tone words):
- Energy the footage supports (mean motion from `footage/footage.json`) and the references' pace:

## Decisions
| Item | Decision | Evidence |
|---|---|---|
| Theme row (section 4), plus at most one contrast theme | | two sentences |
| Background colour (hex) | | |
| Primary colour (hex) | | |
| Accent colour (hex) | | |
| Text colour (hex) | | |
| Brand face (one) | | 3 candidates rendered on a real frame, picked at 25% scale |
| Display face (optional, one) | | |
| Median shot length: intro / build / drop / ending | | |
| Transitions allowed (from the section 3 list) | | |
| Grade approach | | |
| Sound palette | | |
| Music genre and BPM range | | |

## Thumbnail
| Item | Decision |
|---|---|
| Subject | |
| Mood | |
| Colours | |
| Lettering style | |

## Not this (from the client's dislikes)
-

## Style frame
- One finished still (real frame + type + grade): `jobs/{job}/style/style_frame.png`
- One thumbnail sketch: `jobs/{job}/style/thumb_sketch.png`

## Gate
- [ ] The user approved this page and the style frame on: (date)
