/**
 * Parses the two sanctioned zotero:// deep-link families the knowledge site
 * may carry (see the topic-tree spec): `open-pdf` and `select`, over the user
 * library or a group library, targeting items or collections. Anything else
 * returns null and falls through to the OS protocol handler.
 */

export interface ZoteroDeepLink {
  action: "open-pdf" | "select";
  library: { kind: "user" } | { kind: "group"; groupID: number };
  objectKind: "items" | "collections";
  key: string;
  page?: number;
}

const LINK = new RegExp(
  "^zotero://(open-pdf|select)/"
  + "(library|groups/(\\d+))/"
  + "(items|collections)/"
  + "([A-Za-z0-9]+)"
  + "(?:\\?(.*))?$",
  "u",
);

export function parseZoteroLink(spec: string): ZoteroDeepLink | null {
  const match = LINK.exec(spec.trim());
  if (!match) return null;
  const [, action, libraryPart, groupID, objectKind, key, query] = match;
  const link: ZoteroDeepLink = {
    action: action as ZoteroDeepLink["action"],
    library: libraryPart === "library"
      ? { kind: "user" }
      : { kind: "group", groupID: Number(groupID) },
    objectKind: objectKind as ZoteroDeepLink["objectKind"],
    key: key!,
  };
  if (query) {
    const page = /(?:^|&)page=([^&]*)/u.exec(query)?.[1];
    if (page !== undefined) {
      const value = Number(page);
      if (!Number.isSafeInteger(value) || value < 1) return null;
      link.page = value;
    }
  }
  return link;
}
