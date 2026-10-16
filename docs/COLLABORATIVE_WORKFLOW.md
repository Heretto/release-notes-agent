# Collaborative release-notes workflow

A job is no longer a one-shot "Jira tickets in, one DITA file out" run. It is a **release**
that the agent drafts and the writer then finishes with the agent in a workspace.

## Pipeline (one job run)

| Stage | What happens | Persisted as |
|---|---|---|
| `fetch_issues` | Run the instruction set's JQL. Snapshot every issue with a content hash. | `job_jira_issues` |
| `evaluate` | The analysis agent reads issues in batches and decides, per issue, whether it carries a change end users need to know about, and lists the candidate notes (an issue can yield several). | `job_jira_issues.relevance` |
| `consolidate` | One pass over all candidates to merge duplicates and fix the final list; each note keeps the keys of every issue it came from. | `release_note_items` + `release_note_item_issues` |
| `organize` | The analysis agent groups and orders the notes following the instruction set's organization guidance. | `release_note_items.group_name` / `position` |
| `write` | The writer agent writes the body of one note per item — DITA elements with no wrapper; each is validated. | `release_note_items.dita_content` |
| `assemble` | Notes are placed into topics according to the chunking strategy (`single`, `by_group`, `by_component`), every topic is DTD-validated, and a download artifact is written per topic. | `release_note_topics`, `job_artifacts` |
| `publish` | Optional: topics go to Heretto (create on first publish, update afterwards). | `release_note_topics.heretto_doc_id` |

Progress is reported on the job (`stage`, `stage_message`) and polled by the UI.

## Rerun

`POST /jobs/{id}/rerun` runs the pipeline again **on the same job**:

- An issue whose content hash is unchanged is left alone, and so are its notes.
- A changed issue gets a `jira_changed` history entry on every note it feeds, with a field-level
  diff. If none of those notes has been edited by a person, the note is rewritten and the
  previous content kept in its history; otherwise the note is flagged for attention and left as
  the person wrote it.
- A new issue is evaluated and written like a first run.
- An issue that no longer matches the query is kept (`in_query = false`) and its notes are flagged.

Topics are re-assembled afterwards with the job's current chunking strategy.

## Workspace

`/releases/{id}/workspace` — the collaboration UI (the route was `/jobs/...` before the
rename; the old paths still redirect). The REST API keeps its `/jobs` prefix:

- Left: the notes, grouped, with status and attention badges. Clicking a note highlights it in the
  rendered topic and opens its details.
- Centre: the assembled topic(s), rendered with `<hop-dita-content>` (server-side
  `DitaRenderer`), or the raw XML. A chunking selector re-splits the notes into topics.
- Right: `Chat | Details`. Chat talks to the writer agent; Details shows the selected note —
  Status and Group fields, then a free-text **Notes** field (a person's own context, open
  questions and links; URLs in it are linked, and it never reaches the assembled topic),
  then tabs for `Jira`, `DITA` and `History`.

The chat agent edits through tools (`update_note`, `set_note_status`, `move_note`,
`reorganize_topics`, `create_note`, `read_issue`), so every change it makes is a recorded,
reversible history event on the affected note.

## Instruction set

An instruction set now names a **writer agent** (required: writes the DITA and runs the chat)
and an optional **analysis agent** (evaluates and organizes; falls back to the writer), a
product name, relevance guidance, organization guidance, and a default chunking strategy.
