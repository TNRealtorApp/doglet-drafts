# Doglet Drafts

Mobile-first draft viewer/editor. Doglet creates drafts via API, sends Jim a URL, he views/edits/shares from his phone.

## API

- `POST /api/drafts` — Create draft
- `GET /d/{id}` — View draft
- `PUT /api/drafts/{id}` — Update draft
- `DELETE /api/drafts/{id}` — Delete draft
- `GET /health` — Health check
