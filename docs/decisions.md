# Project decisions

Agreed choices and rules for this project, newest last. Each entry: `## D-n · date · title`, then Tags / Decision / Why (and Supersedes when it replaces an older one). Edit freely; the AI reads it through wridge `project_memory`.

## D-1 · 2026-11-10 · Garden weather is offline only
Tags: garden, weather
Decision: No network for weather. Day/night follows the real clock. It rains once every hour for 15 minutes; the start minute is random per hour (seeded by date+hour so a restart shows the same weather). Rain can fall by day or by night.
Why: User chose a fully offline, self-cycling weather (2026-11-10) over a real-weather API that needs location.
