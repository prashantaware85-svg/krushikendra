# ai/ — Placeholder (Step 5)

Future home of the Python AI layer:

- RAG-based agriculture knowledge system (PostgreSQL + pgvector)
- AI Krushi Mitra assistant
- Crop disease / image analysis

## Planned layout (not implemented in Step 1)

```
ai/
├── README.md
├── requirements.txt     # langchain, pgvector, vision deps (Step 5)
├── rag/                 # ingestion, retrieval, prompts
└── vision/              # disease/image models
```

> Do NOT implement anything here in Step 1. The backend exposes no AI
> endpoints yet; integration will be scoped in Step 5.
