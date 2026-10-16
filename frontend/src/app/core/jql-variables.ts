/**
 * `{name}` variables in an instruction set's JQL template, for display only.
 *
 * The browser never builds the query that runs. It splits a template so the editor can show
 * which parts are variables and the start dialog can preview what a run will search for; the
 * server resolves the real query, injecting each value as a quoted literal
 * (backend/app/services/jql_variables.py). Keep the token pattern here in step with
 * VAR_PATTERN there.
 */

const TOKEN_SPLIT = /(\{[A-Za-z_][\w-]*\})/g;
const TOKEN_NAME = /^\{([A-Za-z_][\w-]*)\}$/;

export interface JqlVariableSpec {
  label: string;
  default: string;
  hint: string;
}

/** One piece of a split template: literal text, a filled value, or an unfilled token. */
export interface JqlPart {
  text: string;
  isText?: boolean;
  /** A variable with a value — rendered as the value itself. */
  isVar?: boolean;
  /** A variable with nothing to show — rendered as the raw `{token}`. */
  isEmpty?: boolean;
}

/** Every variable in the template, de-duplicated, in first-appearance order. */
export function variableNames(jql: string): string[] {
  const names: string[] = [];
  for (const part of (jql || '').split(TOKEN_SPLIT)) {
    const match = TOKEN_NAME.exec(part);
    if (match && !names.includes(match[1])) names.push(match[1]);
  }
  return names;
}

/**
 * The template split for rendering. With no `values`, every token comes back as `isEmpty`
 * so the editor and the cards can highlight them; with values, a filled token becomes
 * `isVar` carrying the value and an unfilled one stays `isEmpty`.
 */
export function jqlParts(jql: string, values?: Record<string, string>): JqlPart[] {
  return (jql || '')
    .split(TOKEN_SPLIT)
    .filter(part => part !== '')
    .map(part => {
      const match = TOKEN_NAME.exec(part);
      if (!match) return { text: part, isText: true };
      if (!values) return { text: part, isEmpty: true };
      const value = (values[match[1]] || '').trim();
      return value ? { text: value, isVar: true } : { text: part, isEmpty: true };
    });
}

/** Variables with no non-blank value — what blocks starting a release. */
export function missingValues(jql: string, values: Record<string, string>): string[] {
  return variableNames(jql).filter(name => !(values[name] || '').trim());
}

/** The default of each variable, for pre-filling the start form. */
export function defaultsOf(variables: Record<string, JqlVariableSpec> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [name, spec] of Object.entries(variables || {})) out[name] = spec?.default || '';
  return out;
}
