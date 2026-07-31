import type { ChatEntry } from "./sidebar";

export type LibrarySubjectKey = `library:${string}`;

export interface LibraryConversationSubjectInput {
  libraryID: number | string;
  libraryName: string;
}

export interface LibraryConversationSubject extends LibraryConversationSubjectInput {
  key: LibrarySubjectKey;
}

export interface LibraryContextItem {
  key: string;
  itemType: string;
  title: string;
  creators: string;
  year: string;
  doi: string;
}

export interface LibraryMessageContext {
  libraryID: number | string;
  libraryName: string;
  collection: { key: string; path: string } | null;
  selectedItems: readonly LibraryContextItem[];
  omittedItemCount: number;
}

export interface LibraryConversationState {
  subject: LibraryConversationSubject;
  threadId: string | null;
  entries: readonly ChatEntry[];
  opening: boolean;
  running: boolean;
  activeTurnId: string | null;
  error: string | null;
}

export function snapshotLibraryMessageContext(
  context: LibraryMessageContext,
): Readonly<LibraryMessageContext> {
  const collection = context.collection
    ? Object.freeze({ ...context.collection })
    : null;
  const selectedItems = Object.freeze(
    context.selectedItems.map((item) => Object.freeze({ ...item })),
  );
  return Object.freeze({
    libraryID: context.libraryID,
    libraryName: context.libraryName,
    collection,
    selectedItems,
    omittedItemCount: context.omittedItemCount,
  });
}

export function librarySubjectKey(subject: Pick<LibraryConversationSubjectInput, "libraryID">): LibrarySubjectKey {
  return `library:${String(subject.libraryID)}`;
}

export function libraryReaderContext(subject: LibraryConversationSubjectInput): LibraryMessageContext {
  return Object.freeze({
    libraryID: subject.libraryID,
    libraryName: subject.libraryName,
    collection: null,
    selectedItems: Object.freeze([]),
    omittedItemCount: 0,
  });
}
