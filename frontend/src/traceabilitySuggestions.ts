export interface SuggestionArtifact {
  id: string;
  type: "requirement" | "task" | "bug" | "test_case" | "sprint";
  label: string;
  text: string;
  defaultRelationship: string;
}

export interface RankedSuggestion extends SuggestionArtifact {
  score: number;
  similarity: number;
  matchedTerms: string[];
  sharedTerms: string[];
  matchedConcepts: string[];
  semanticSimilarity: number;
  relationshipType: string;
  selected?: boolean;
}

export function relationshipOptions(artifactType: SuggestionArtifact["type"]): string[] {
  const options: Record<SuggestionArtifact["type"], string[]> = {
    requirement: ["depends_on", "implements", "validates", "affects", "associated_with"],
    task: ["implements", "belongs_to", "associated_with"],
    bug: ["affects", "validates", "associated_with"],
    test_case: ["validates", "associated_with"],
    sprint: ["belongs_to", "associated_with"],
  };
  return options[artifactType] ?? ["associated_with"];
}

function tokenize(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((token) => token.length > 2)
  );
}

function jaccardSimilarity(setA: Set<string>, setB: Set<string>): number {
  if (setA.size === 0 && setB.size === 0) return 1;
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersection = 0;
  for (const item of setA) {
    if (setB.has(item)) intersection++;
  }
  const union = setA.size + setB.size - intersection;
  return intersection / union;
}

function extractConcepts(text: string): Set<string> {
  const tokens = tokenize(text);
  const concepts = new Set<string>();
  for (const token of tokens) {
    if (token.length >= 4) {
      concepts.add(token);
    }
  }
  return concepts;
}

export function isPotentialDuplicateRequirement(suggestion: RankedSuggestion): boolean {
  return suggestion.type === "requirement" && suggestion.similarity > 0.7;
}

export function rankTraceabilitySuggestions(
  queryText: string,
  candidates: SuggestionArtifact[],
  maxResults: number
): RankedSuggestion[] {
  const queryTokens = tokenize(queryText);
  const queryConcepts = extractConcepts(queryText);
  if (queryTokens.size === 0) return [];

  const scored = candidates.map((candidate) => {
    const candidateTokens = tokenize(candidate.text);
    const candidateConcepts = extractConcepts(candidate.text);

    const similarity = jaccardSimilarity(queryTokens, candidateTokens);
    const semanticSimilarity = jaccardSimilarity(queryConcepts, candidateConcepts);

    const matchedTerms = Array.from(queryTokens).filter((token) => candidateTokens.has(token));
    const sharedTerms = Array.from(queryTokens).filter((token) => candidateTokens.has(token)).slice(0, 5);
    const matchedConcepts = Array.from(queryConcepts).filter((concept) => candidateConcepts.has(concept)).slice(0, 5);

    return {
      ...candidate,
      score: similarity,
      similarity,
      matchedTerms,
      sharedTerms,
      matchedConcepts,
      semanticSimilarity,
      relationshipType: candidate.defaultRelationship,
    };
  });

  scored.sort((a, b) => b.similarity - a.similarity);
  return scored.slice(0, maxResults);
}