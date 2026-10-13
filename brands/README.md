# Brand cache

One folder per brand slug, written by the pipeline:

```
brands/<slug>/
├── kit.json              # official channels, logo, colors, screenshots (PROJECT.md §9.2)
├── logo/                 # svg/png, transparent
├── assets/approved/      # human-approved assets, reused across network/country variants
└── runs/<timestamp>/manifest.json
```

Everything except this README is git-ignored. Approved assets are never deleted by the pipeline.
