## main

## v4.2.0 / 2023-12-11
 - Add esi-utils-comcat to install.
 - Fix install bug -- package dependency on daemon should have been python-daemon.
 - Rev versions of esi-shakelib and shakemap-modules in pyproject.toml.
 - Add versioning info for shake to pass to the model module.
 - Modify source_environment.yml to have more flexible python version.
 - Fixes to install.sh; no longer use deployment.txt files.
 - Made tests work.
 - Modified to use pypi-based esi-shakelib and shakemap-modules.
 - Restructured code to move code into "src" directory.
 - Changed to pyproject.toml
 - Removed c directory and refactored to use esi-core.
 - Modified to allow RotD50 as an input component type.
 - Added CHANGELOG.md

## 4.1.6 / 2023-12-08
 - Fix transfer_email to work with encripter servers.
 - Bug fixes: Fix order of quotes in multigmpe.py that was disrupted by black
   formatter; fix HotSpot vs Volcanic issue in probs.py; add alpha-shapes to install.

## 4.1.5 / 2023-08-29
 - Upudate docs so that the HTML isn't tracked in the repo and will build with gitlab pipelines.
 - Fix vertical/horizontal orientation bug in station.py.
 - Modified to allow RotD50 as an input component type.
 - Added CHANGELOG.md
 - Improved support for "points" mode ShakeMap runs - `assemble -p` change and `makecsv` module.
 - Added optional persistence of version history in the sm_create command.

