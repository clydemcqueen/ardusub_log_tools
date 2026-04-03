# GUIT
Commit: abe1721cf5

Experimental, from https://github.com/clydemcqueen/ardusub_surftrak/blob/guided_above_terrain/lua/transect3.lua
This table is typically produced by a Lua script and contains surface tracking information.

| Field | Units | Description |
|---|---|---|
| RFTarg | m | Rangefinder target |
| RFRead | m | Rangefinder reading |
| Head | rad | Heading (Yaw) |
| RFOk | boolean | Rangefinder valid (1 = valid, 0 = invalid) |
| SubT | m | Sub's rangefinder target |
| Succ | boolean | Success flag (1 = success, 0 = failure) |
