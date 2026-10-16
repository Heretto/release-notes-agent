"""JQL query variables: `{name}` tokens an instruction set fills in per release.

An instruction set stores a JQL *template* — `project = HER AND fixVersion = {version}` —
plus metadata for each token (a label, a default, a hint). Starting a release supplies a
value per token and the server resolves the template into the query that actually runs.

Resolution happens here, on the server, and never in the browser: the value a person types
is untrusted input that ends up inside a query. A naive `jql.replace("{version}", value)` —
which is what the design prototype does — lets a value like `1.0" OR project = "SECRET`
rewrite the query and read another project's issues.

The rule that makes that safe: **a value is always injected as one quoted JQL string
literal**, with backslashes and double quotes escaped. A token already wrapped in quotes in
the template has those quotes absorbed, so both of these

    fixVersion = {version}
    fixVersion = "{version}"

resolve to `fixVersion = "4.12"`. A value can therefore never close its own literal, and it
cannot contribute operators or field names — the worst a hostile value can do is fail to
match anything.
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping

#: A variable token. Deliberately the same shape the design uses: a leading letter or
#: underscore, then word characters or hyphens.
VAR_PATTERN = r"[A-Za-z_][\w-]*"

#: Matches a bare token, optionally wrapped in double quotes, so the quotes can be absorbed
#: rather than nested when the value is injected as a literal.
_TOKEN_RE = re.compile(r'"?\{(' + VAR_PATTERN + r')\}"?')

#: Matches a bare token only — used for listing, where surrounding quotes are irrelevant.
_NAME_RE = re.compile(r"\{(" + VAR_PATTERN + r")\}")


def variable_names(jql: str) -> List[str]:
    """Every variable in the template, de-duplicated, in first-appearance order."""
    seen: List[str] = []
    for match in _NAME_RE.finditer(jql or ""):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def escape_value(value: str) -> str:
    """A value as the inside of a JQL double-quoted string literal.

    Backslash first, or escaping the quote would then have its own backslash escaped.
    """
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def missing_values(jql: str, values: Mapping[str, str]) -> List[str]:
    """Variables the template needs that have no non-blank value."""
    return [name for name in variable_names(jql) if not (values.get(name) or "").strip()]


def resolve(jql: str, values: Mapping[str, str]) -> str:
    """The query to actually run, with every value injected as a quoted literal.

    Raises ValueError when a variable has no value: running a query with an unresolved
    `{token}` in it would silently search for the literal text.
    """
    missing = missing_values(jql, values)
    if missing:
        raise ValueError(f"No value given for: {', '.join(missing)}")

    def substitute(match: re.Match) -> str:
        return '"' + escape_value((values.get(match.group(1)) or "").strip()) + '"'

    return _TOKEN_RE.sub(substitute, jql or "")


#: A Jira project key. Jira's own rule is letters, digits and underscore starting with a
#: letter; anything else cannot be a key, so refusing it keeps the unquoted `project = X`
#: below from being a way to smuggle JQL in.
_PROJECT_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def release_query(project: str, release: str, extra_jql: str | None = None) -> str:
    """The query for one Jira release, in an instruction set's "releases" source mode.

    The release name is a Jira value like any other and is injected as a quoted literal.
    `extra_jql` is written by whoever configured the instruction set — the same trust as the
    JQL template itself — but it is wrapped in parentheses so an `OR` inside it widens only
    the filter and can never widen the query past the chosen fixVersion.
    """
    project = (project or "").strip().upper()
    if not _PROJECT_KEY_RE.match(project):
        raise ValueError(f"'{project}' is not a Jira project key")
    if not (release or "").strip():
        raise ValueError("No release chosen")

    query = f'project = {project} AND fixVersion = "{escape_value(release.strip())}"'
    extra = (extra_jql or "").strip()
    if extra:
        query += f" AND ({extra})"
    return query + " ORDER BY created ASC"


def normalize_specs(jql: str, specs: Mapping[str, Mapping[str, str]] | None) -> Dict[str, Dict[str, str]]:
    """Variable metadata, keyed by the tokens the template actually contains.

    Metadata for a token no longer in the query is dropped and a new token starts blank, so
    the stored shape can never drift from the template it describes.
    """
    specs = specs or {}
    normalized: Dict[str, Dict[str, str]] = {}
    for name in variable_names(jql):
        spec = specs.get(name) or {}
        normalized[name] = {
            "label": (spec.get("label") or "").strip(),
            "default": (spec.get("default") or "").strip(),
            "hint": (spec.get("hint") or "").strip(),
        }
    return normalized


def defaults_of(specs: Mapping[str, Mapping[str, str]] | None) -> Dict[str, str]:
    """The default value of each variable, for pre-filling the start-a-release form."""
    return {name: (spec.get("default") or "") for name, spec in (specs or {}).items()}


#: The key a releases-mode run records its chosen release under, so `jobs.variables` reads
#: the same way in both source modes.
RELEASE_VARIABLE = "fixVersion"


def query_for_job(job) -> str:
    """The query this release should run **now**, from its instruction set as it stands.

    A release stores the query it resolved at the time, so an instruction set edited since
    — a corrected JQL template, a different project, a new filter — would otherwise never
    reach a rerun. This rebuilds it from the current template and the values the release
    already recorded.

    Three cases keep the stored query instead:

    * the query did not come from the instruction set (`uses_instruction_query` false),
      so it is the caller's own and not ours to rewrite;
    * the instruction set is gone;
    * the template now needs a variable the release has no value for. Rebuilding would
      raise, and refusing to run is a worse answer than running what it ran last time —
      the Edit release dialog is where the missing value gets filled in.
    """
    if not getattr(job, "uses_instruction_query", True):
        return job.jql_query

    instruction_set = job.instruction_set
    if instruction_set is None:
        return job.jql_query

    values = dict(job.variables or {})
    try:
        if (instruction_set.source_mode or "jql") == "releases":
            release = values.get(RELEASE_VARIABLE, "")
            return release_query(
                instruction_set.jira_project or "", release, instruction_set.extra_jql
            )
        return resolve(instruction_set.jql_query or "", values)
    except ValueError:
        return job.jql_query
