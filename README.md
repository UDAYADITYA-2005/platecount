# PlateCount

> All code in this repository was written during the Meta Global AI Developer Hackathon,
> from Oct 30, 2026. See PROGRESS.md for the dated log.

PlateCount counts bacterial colonies on agar plate photos and reports a CFU/mL estimate.
An agent built on Muse Spark checks SAM 3.1's segmentation, re-checks doubtful regions, and
refuses to report any number that no tool produced.

_Full README written on Day 5._

## Data credit

Demo plates and the benchmark use the [AGAR dataset](https://agar.neurosys.com), CC BY-NC 2.0.
No AGAR files are in this repository: the committed demo results hold numbers and boxes only.
