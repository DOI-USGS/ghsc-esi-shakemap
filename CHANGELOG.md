## main

## 4.1.6 / 2023-12-05
 - Bug fixes: Fix order of quotes in multigmpe.py that was disrupted by black
   formatter; fix HotSpot vs Volcanic issue in probs.py.

## 4.1.5 / 2023-08-29
 - Upudate docs so that the HTML isn't tracked in the repo and will build with gitlab pipelines.
 - Fix vertical/horizontal orientation bug in station.py.
 - Modified to allow RotD50 as an input component type.
 - Added CHANGELOG.md
 - Improved support for "points" mode ShakeMap runs - `assemble -p` change and `makecsv` module.
 - Added optional persistence of version history in the sm_create command.
