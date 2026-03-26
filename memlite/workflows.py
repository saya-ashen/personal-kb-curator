import re
from datetime import date
from pathlib import Path
from typing import Any

from dedup import (
    run_dedup_eval as _run_dedup_eval,
    dedup_merge as run_dedup_merge,
    dedup_rollback as run_dedup_rollback,
    dedup_scan as run_dedup_scan,
)
from frontmatter import parse_frontmatter
from intake import import_document as intake_import_document
from indexer import build_index
from knowledge_store import (
    create_note,
    list_documents,
    now_iso,
    persist_doc_edges,
    sync_documents_to_db,
)
from rag import ask_with_citations


def _clean_words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def _infer_title(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else "Quick capture"
    words = _clean_words(first_line)
    return " ".join(words[:10]) or "Quick capture"


def _infer_summary(text: str) -> str:
    sentence = re.split(r"[。.!?]\s*", text.strip())[0]
    words = _clean_words(sentence)
    return " ".join(words[:20])


def _extract_tags(text: str) -> list[str]:
    tags = {m.group(1).lower() for m in re.finditer(r"#([A-Za-z0-9_-]+)", text)}
    return sorted(tags)


def _extract_people(text: str) -> list[str]:
    people = {m.group(1) for m in re.finditer(r"@([A-Za-z][A-Za-z0-9_-]+)", text)}
    return sorted(people)


def _extract_projects(text: str) -> list[str]:
    projects = set()
    for m in re.finditer(
        r"(?:project|项目)\s+([A-Za-z0-9_-]+)", text, flags=re.IGNORECASE
    ):
        projects.add(m.group(1))
    return sorted(projects)


def _extract_topics(text: str) -> list[str]:
    keywords = []
    for token in re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", text.lower()):
        if token in {
            "today",
            "with",
            "this",
            "that",
            "project",
            "我们",
            "今天",
            "讨论",
            "决定",
        }:
            continue
        keywords.append(token)
    return sorted(set(keywords[:8]))


def capture_text(
    workspace_root: Path, text: str, source: str = "manual"
) -> dict[str, Any]:
    title = _infer_title(text)
    summary = _infer_summary(text)
    tags = _extract_tags(text)
    projects = _extract_projects(text)
    people = _extract_people(text)
    topics = _extract_topics(text)

    created = create_note(
        workspace_root=workspace_root,
        zone="notes",
        payload={
            "title": title,
            "type": "note",
            "summary": summary,
            "tags": tags,
            "topics": topics,
            "projects": projects,
            "people": people,
            "source": source,
            "confidence": "medium",
            "related": [],
            "body": text.strip(),
        },
    )
    index_result = build_index(workspace_root)
    return {
        **created,
        "summary": summary,
        "extracted_metadata": {
            "tags": tags,
            "topics": topics,
            "projects": projects,
            "people": people,
        },
        "index": index_result,
    }


def import_document(
    workspace_root: Path,
    path_or_url: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    imported = intake_import_document(
        workspace_root=workspace_root,
        path_or_url=path_or_url,
        options=options,
    )
    index_result = build_index(workspace_root)
    return {**imported, "index": index_result}


def dedup_scan(
    workspace_root: Path,
    threshold_profile: dict[str, float] | None = None,
) -> dict[str, Any]:
    return run_dedup_scan(
        workspace_root=workspace_root,
        threshold_profile=threshold_profile,
    )


def dedup_merge(
    workspace_root: Path,
    group_id_or_doc_ids: str | list[str],
    mode: str = "auto",
) -> dict[str, Any]:
    return run_dedup_merge(
        workspace_root=workspace_root,
        group_id_or_doc_ids=group_id_or_doc_ids,
        mode=mode,
    )


def dedup_rollback(workspace_root: Path, merge_id: str) -> dict[str, Any]:
    return run_dedup_rollback(workspace_root=workspace_root, merge_id=merge_id)


def run_dedup_eval(workspace_root: Path, labeled_pairs_path: Path) -> dict[str, Any]:
    return _run_dedup_eval(
        workspace_root=workspace_root,
        labeled_pairs_path=labeled_pairs_path,
    )


def _is_capture_source(workspace_root: Path, value: str) -> bool:
    if re.match(r"^https?://", value.strip(), flags=re.IGNORECASE):
        return True
    raw_path = Path(value)
    if raw_path.is_absolute() and raw_path.exists():
        return True
    return (workspace_root / raw_path).exists()


def capture(workspace_root: Path, input_value: str) -> dict[str, Any]:
    if _is_capture_source(workspace_root, input_value):
        return import_document(workspace_root=workspace_root, path_or_url=input_value)
    return capture_text(workspace_root=workspace_root, text=input_value)


def ask_question(
    workspace_root: Path,
    question: str,
    filters: dict[str, Any] | None = None,
    use_cloud_generation: bool = False,
    cloud_generator: Any | None = None,
) -> dict[str, Any]:
    if not (workspace_root / "rag" / "index" / "chunks.jsonl").exists():
        build_index(workspace_root)
    return ask_with_citations(
        workspace_root=workspace_root,
        question=question,
        filters=filters,
        limit=8,
        use_cloud_generation=use_cloud_generation,
        cloud_generator=cloud_generator,
    )


def _extract_by_prefix(text: str, prefixes: tuple[str, ...]) -> list[str]:
    entries: list[str] = []
    pattern = (
        r"(?:^|[\n\r\.]\s*)(?:"
        + "|".join(re.escape(p) for p in prefixes)
        + r")\s*(.+?)\s*(?=$|[\n\r\.])"
    )
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        value = match.group(1).strip()
        if value:
            entries.append(value)
    return entries


def _ensure_project_note(
    workspace_root: Path,
    project: str,
    meeting_title: str,
    decisions: list[str],
    action_items: list[str],
) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", project.lower()).strip("-") or "project"
    path = workspace_root / "projects" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    section_lines = [f"- Meeting: {meeting_title}"]
    if decisions:
        section_lines.append(f"- Decisions: {'; '.join(decisions)}")
    if action_items:
        section_lines.append(f"- Action items: {'; '.join(action_items)}")
    section = "\n".join(section_lines)

    if path.exists():
        current = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(current)
        updated = body.strip() + "\n\n## Meeting updates\n" + section + "\n"
        path.write_text(
            f"---\n"
            f'id: "{meta.get("id", f"project-{slug}")}"\n'
            f'title: "{meta.get("title", project)}"\n'
            f'created_at: "{meta.get("created_at", now_iso())}"\n'
            f'updated_at: "{now_iso()}"\n'
            f'type: "project"\n'
            f'summary: "{meta.get("summary", "")}"\n'
            f"tags: []\n"
            f"topics: []\n"
            f'projects: ["{project}"]\n'
            f"people: []\n"
            f'source: "meeting"\n'
            f'confidence: "medium"\n'
            f"related: []\n"
            f'status: "active"\n'
            f"owners: []\n"
            f"milestones: []\n"
            f'last_reviewed_at: "{now_iso()}"\n'
            f"---\n\n{updated}",
            encoding="utf-8",
        )
    else:
        body = "# Project context\n\n## Meeting updates\n" + section + "\n"
        path.write_text(
            "---\n"
            f'id: "project-{slug}"\n'
            f'title: "{project}"\n'
            f'created_at: "{now_iso()}"\n'
            f'updated_at: "{now_iso()}"\n'
            'type: "project"\n'
            f'summary: "Project page for {project}"\n'
            "tags: []\n"
            "topics: []\n"
            f'projects: ["{project}"]\n'
            "people: []\n"
            'source: "meeting"\n'
            'confidence: "medium"\n'
            "related: []\n"
            'status: "active"\n'
            "owners: []\n"
            "milestones: []\n"
            f'last_reviewed_at: "{now_iso()}"\n'
            f"---\n\n{body}",
            encoding="utf-8",
        )

    return str(path.relative_to(workspace_root))


def process_meeting(
    workspace_root: Path, text: str, meeting_date: str
) -> dict[str, Any]:
    title = f"Meeting {meeting_date} - {_infer_title(text)}"
    summary = _infer_summary(text)
    projects = _extract_projects(text)
    participants = _extract_people(text)
    decisions = _extract_by_prefix(text, ("Decision:", "Decisions:", "决策:", "决定:"))
    action_items = _extract_by_prefix(text, ("Action:", "Actions:", "行动项:", "待办:"))

    body = (
        "## Summary\n"
        f"{summary}\n\n"
        "## Decisions\n"
        + ("\n".join(f"- {d}" for d in decisions) if decisions else "- none")
        + "\n\n## Action Items\n"
        + ("\n".join(f"- {a}" for a in action_items) if action_items else "- none")
        + "\n\n## Raw Notes\n"
        + text.strip()
        + "\n"
    )

    created = create_note(
        workspace_root=workspace_root,
        zone="meetings",
        payload={
            "title": title,
            "type": "meeting",
            "summary": summary,
            "topics": _extract_topics(text),
            "projects": projects,
            "people": participants,
            "source": "meeting",
            "meeting_date": meeting_date,
            "participants": participants,
            "decisions": decisions,
            "action_items": action_items,
            "body": body,
        },
    )

    changed_files = [created["note_path"]]
    for project in projects:
        changed_files.append(
            _ensure_project_note(
                workspace_root=workspace_root,
                project=project,
                meeting_title=title,
                decisions=decisions,
                action_items=action_items,
            )
        )

    index_result = build_index(workspace_root)
    return {
        "meeting_path": created["note_path"],
        "summary": summary,
        "decisions": decisions,
        "action_items": action_items,
        "changed_files": changed_files,
        "index": index_result,
    }


def _in_period(created_at: str, period_start: str, period_end: str) -> bool:
    try:
        created = date.fromisoformat(created_at[:10])
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
    except ValueError:
        return False
    return start <= created <= end


def generate_weekly_review(
    workspace_root: Path, period_start: str, period_end: str
) -> dict[str, Any]:
    highlights: list[str] = []
    key_decisions: list[str] = []
    open_items: list[str] = []
    sources: list[str] = []

    for zone in ["notes", "meetings"]:
        zone_dir = workspace_root / zone
        if not zone_dir.exists():
            continue
        for file_path in sorted(zone_dir.glob("*.md")):
            text = file_path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            if not _in_period(
                str(meta.get("created_at", "")), period_start, period_end
            ):
                continue
            title = str(meta.get("title", file_path.stem))
            highlights.append(title)
            sources.append(str(file_path.relative_to(workspace_root)))
            for decision in meta.get("decisions", []):
                key_decisions.append(str(decision))
            for item in meta.get("action_items", []):
                open_items.append(str(item))

    next_week = [
        "Close high-priority action items first.",
        "Promote repeated meeting decisions into project pages.",
    ]
    body = (
        "## Weekly Highlights\n"
        + ("\n".join(f"- {h}" for h in highlights) if highlights else "- none")
        + "\n\n## Key Decisions\n"
        + ("\n".join(f"- {d}" for d in key_decisions) if key_decisions else "- none")
        + "\n\n## Unfinished Items\n"
        + ("\n".join(f"- {o}" for o in open_items) if open_items else "- none")
        + "\n\n## Suggestions Next Week\n"
        + "\n".join(f"- {s}" for s in next_week)
        + "\n"
    )

    review = create_note(
        workspace_root=workspace_root,
        zone="reviews",
        payload={
            "title": f"Weekly Review {period_start} to {period_end}",
            "type": "review",
            "summary": f"Weekly synthesis for {period_start} to {period_end}",
            "source": "synthesis",
            "period_start": period_start,
            "period_end": period_end,
            "key_decisions": key_decisions,
            "open_items": open_items,
            "related": sources,
            "body": body,
        },
    )
    build_index(workspace_root)
    return {
        "review_path": review["note_path"],
        "highlights": highlights,
        "key_decisions": key_decisions,
        "open_items": open_items,
        "next_week_suggestions": next_week,
        "sources": sources,
    }


def _normalize_meta_values(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    normalized: set[str] = set()
    for item in value:
        text = str(item).strip().lower()
        if text:
            normalized.add(text)
    return normalized


def _created_at_key(value: str) -> str:
    raw = value.strip()
    if not raw:
        return "9999-12-31T23:59:59Z"
    return raw


def run_graph_enrichment(workspace_root: Path, limit: int = 500) -> dict[str, Any]:
    all_documents = list_documents(workspace_root)
    sorted_documents = sorted(
        all_documents,
        key=lambda doc: (
            _created_at_key(str(doc.get("meta", {}).get("created_at", ""))),
            str(doc.get("doc_id", "")),
        ),
    )
    selected_documents = sorted_documents[: max(1, int(limit))]

    sync_documents_to_db(workspace_root)

    candidate_edges: list[dict[str, Any]] = []

    for left_index, left in enumerate(selected_documents):
        left_meta = dict(left.get("meta", {}))
        left_doc_id = str(left.get("doc_id", "")).strip()
        if not left_doc_id:
            continue

        left_topics = _normalize_meta_values(left_meta.get("topics", []))
        left_projects = _normalize_meta_values(left_meta.get("projects", []))
        left_created_at = str(left_meta.get("created_at", "")).strip()

        for right in selected_documents[left_index + 1 :]:
            right_meta = dict(right.get("meta", {}))
            right_doc_id = str(right.get("doc_id", "")).strip()
            if not right_doc_id or right_doc_id == left_doc_id:
                continue

            right_topics = _normalize_meta_values(right_meta.get("topics", []))
            right_projects = _normalize_meta_values(right_meta.get("projects", []))
            shared_topics = sorted(left_topics & right_topics)
            shared_projects = sorted(left_projects & right_projects)

            if shared_topics:
                src_doc_id, dst_doc_id = sorted([left_doc_id, right_doc_id])
                candidate_edges.append(
                    {
                        "src_doc_id": src_doc_id,
                        "dst_doc_id": dst_doc_id,
                        "edge_type": "same_topic",
                        "weight": float(len(shared_topics)),
                        "evidence": f"topics:{','.join(shared_topics)}",
                    }
                )

            right_created_at = str(right_meta.get("created_at", "")).strip()
            if not left_created_at or not right_created_at:
                continue
            if left_created_at >= right_created_at:
                older_doc_id, newer_doc_id = right_doc_id, left_doc_id
                older_topics, newer_topics = right_topics, left_topics
                older_projects, newer_projects = right_projects, left_projects
            else:
                older_doc_id, newer_doc_id = left_doc_id, right_doc_id
                older_topics, newer_topics = left_topics, right_topics
                older_projects, newer_projects = left_projects, right_projects

            follow_up_topics = sorted(older_topics & newer_topics)
            follow_up_projects = sorted(older_projects & newer_projects)
            if not follow_up_topics and not follow_up_projects:
                continue
            evidence_parts: list[str] = []
            if follow_up_topics:
                evidence_parts.append(f"topics:{','.join(follow_up_topics)}")
            if follow_up_projects:
                evidence_parts.append(f"projects:{','.join(follow_up_projects)}")
            candidate_edges.append(
                {
                    "src_doc_id": older_doc_id,
                    "dst_doc_id": newer_doc_id,
                    "edge_type": "follow_up",
                    "weight": float(len(follow_up_topics) + len(follow_up_projects)),
                    "evidence": "; ".join(evidence_parts),
                }
            )

    deduped_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in candidate_edges:
        key = (
            str(edge["src_doc_id"]),
            str(edge["dst_doc_id"]),
            str(edge["edge_type"]),
        )
        current = deduped_edges.get(key)
        if current is None:
            deduped_edges[key] = edge
            continue
        existing_weight = float(current.get("weight", 0.0))
        next_weight = float(edge.get("weight", 0.0))
        if next_weight >= existing_weight:
            deduped_edges[key] = edge

    persisted = persist_doc_edges(workspace_root, list(deduped_edges.values()))
    return {
        "documents_scanned": len(selected_documents),
        "candidate_edges": len(candidate_edges),
        "new_edges": int(persisted["inserted"]),
        "updated_edges": int(persisted["updated"]),
        "skipped_edges": int(persisted["skipped"]),
    }
