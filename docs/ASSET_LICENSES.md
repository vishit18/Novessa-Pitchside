# Asset licences

Every third-party asset used in the app, repo or demo video goes here before it's used.

| Asset | Source | Licence | Where used | Attribution shown |
|---|---|---|---|---|
| Match footage segment | SoccerTrack v2, huggingface.co/datasets/atomscott/soccertrack-v2 | CC BY 4.0 (check gated conditions) | Real footage mode, demo video | README credits + on-screen credit |
| Fonts | Google Fonts | SIL OFL | Frontend | not required |
| SoccerTrack v2 footage, match 117093, 1st half, 100 s window (`footage/`, not in git) | Hugging Face `atomscott/soccertrack-v2` | CC BY 4.0, pseudonymised | Real footage mode (`vision/`, `/real`) | Required: "Footage: SoccerTrack v2 (CC BY 4.0)" on screen and in the README. Painted university name and crest are removed from the shown clip (`vision/redact.py`). |
| Vision output derived from that footage (`data/real/117093_w1890/`) | Our pipeline | CC BY 4.0 (derived from the above) | Real footage mode | Same credit |
| RT-DETR r50vd detector weights (`PekingU/rtdetr_r50vd`) | Hugging Face | Apache 2.0 | `vision/detect.py` | not required |
| Noto Sans Devanagari | Fontsource / Google Fonts | SIL OFL | Hindi text in the frontend | not required |
| Big Shoulders Display, Figtree | Fontsource (`@fontsource/*`) / Google Fonts | SIL OFL 1.1 | App-wide since look 6 (`frontend/src/index.css`), and `/design-lab` | not required |
| Bricolage Grotesque, Fraunces, Libre Franklin, Archivo, Caveat Brush, Atkinson Hyperlegible | Fontsource (`@fontsource/*`) / Google Fonts | SIL OFL 1.1 | `/design-lab` only (`frontend/src/screens/lab/lab.css`) | not required |

## Citation

SoccerTrack v2 footage and labels: Atom Scott, Ikuma Uchida, Kento Kuroda, Yufi Kim and Keisuke Fujii, *SoccerTrack v2: A Full-Pitch Panoramic Video Dataset for Game State Reconstruction and Ball Action Spotting*, arXiv:2508.01802, 2025. Dataset: huggingface.co/datasets/atomscott/soccertrack-v2 (CC BY 4.0). Code: github.com/AtomScott/SoccerTrack-v2.
