# database/ — see backend Alembic setup (Step 2)

Live schema management lives in `backend/alembic/` (config `backend/alembic.ini`,
migrations `backend/alembic/versions/`). Full guide: `docs/database.md`.

This folder is reserved for future non-migration artefacts:

```
database/
├── README.md   # this file
└── seeds/      # Reference data, e.g. crops, schemes (Step 3+, NOT yet)
```

Step 2 ships exactly one migration: `0001_system_info` (creates the
`system_info` verification table). No business tables yet.
