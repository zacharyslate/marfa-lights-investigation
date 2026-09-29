# Licensing

This repository holds a paper, the code that produces every number in it, the data, and a website. They are licensed as follows.

| What | Where | Licence |
|---|---|---|
| The paper, the Supporting Information, figures, animations, derived data and website text | `publication/`, `data/derived/`, `docs/` (text, figures, `docs/media/`, `docs/data/`), notes | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), full text in [`LICENSE-CC-BY-4.0.txt`](LICENSE-CC-BY-4.0.txt) |
| Code | `analysis/`, the site's own JavaScript and CSS (`docs/assets/*.js`, `*.css`, `docs/app/`, `docs/sw.js`) | [MIT](LICENSE) |
| Photographs by Zach Warren | files beginning `zw_` in `docs/img/`, the photographs reproduced in Fig. 7 of the paper (`fig07_photo_validation`), and the photo crops in `data/derived/photos/` | © Zach Warren. All rights reserved. Not covered by CC BY 4.0 or MIT. Ask the author for permission to reuse. |
| Third-party material | see below | its own licence |

## How to credit

Cite the paper as given on its web page, <https://zacharyslate.github.io/marfa-lights-investigation/paper.html>, including the DOI once one is assigned. For CC BY reuse, give the author (Zach Warren), the title, a link to the source, the licence, and say whether you changed anything.

## Third-party material kept under its own terms

- **Photographs from other people** (`docs/img/`, all files not beginning `zw_` or `fig`): public domain or Creative Commons, as credited in each caption and in [`docs/img/CREDITS.md`](docs/img/CREDITS.md). CC BY 2.0 and CC BY-SA 3.0 images keep those licences.
- **Leaflet** (`docs/assets/leaflet/`): BSD 2-Clause, see its `LICENSE`.
- **Astronomy Engine** (`docs/assets/vendor/astronomy.browser.min.js`): MIT, Don Cross; the notice is in the file header.
- **Bright-star data** (`docs/data/bright_stars.json`): from d3-celestial, BSD 3-Clause, see `docs/data/bright_stars.LICENSE.txt`.
- **Input data** (`data/inputs/`, `data/dem/`): public records from U.S. agencies (USGS 3DEP lidar, TxDOT, FCC, FAA, FRA, EIA, BTS) and UMTRI reports, cited in the paper. The project's licence covers only what was added to them here. Their original terms still apply.
- **Map tiles** shown on the website (USGS The National Map, OpenStreetMap) are loaded from their providers and are not part of this repository.
