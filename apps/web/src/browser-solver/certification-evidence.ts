import type {
  BrowserBenchmarkCaseReport,
  BrowserBenchmarkReport,
} from "./benchmark";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverResult,
} from "./types";

export interface CertificationEvidenceCounts {
  readonly parityFailures: number;
  readonly nondeterministicCases: number;
  readonly timeouts: number;
  readonly invalidCandidates: number;
}

export type CertificationResultValidator = (
  request: BrowserRankedSearchRequest,
  result: BrowserSolverResult,
) => void;

function deterministicSignature(result: BrowserSolverResult): string {
  return JSON.stringify({
    status: result.status,
    candidate: result.candidate,
    selected_variant_ids: result.selected_variant_ids,
    preference_score: result.preference_score,
    decoration_count: result.decoration_count,
  });
}

function profileNondeterministicCaseCount(
  reports: readonly BrowserBenchmarkReport[],
): number {
  const signatures = new Map<
    string,
    { values: Set<string>; internallyNondeterministic: boolean }
  >();
  for (const report of reports) {
    for (const caseReport of report.cases) {
      const current = signatures.get(caseReport.name) ?? {
        values: new Set<string>(),
        internallyNondeterministic: false,
      };
      current.values.add(deterministicSignature(caseReport.result));
      current.internallyNondeterministic ||= !caseReport.deterministic;
      signatures.set(caseReport.name, current);
    }
  }
  return [...signatures.values()].filter(
    ({ values, internallyNondeterministic }) =>
      internallyNondeterministic || values.size > 1,
  ).length;
}

export function summarizeCertificationEvidence(
  profileReports: readonly (readonly BrowserBenchmarkReport[])[],
  additionalCases: readonly BrowserBenchmarkCaseReport[],
  validateResult: CertificationResultValidator,
): CertificationEvidenceCounts {
  const reportCases = profileReports.flatMap((reports) =>
    reports.flatMap((report) => report.cases),
  );
  const allCases = [...reportCases, ...additionalCases];
  let invalidCandidates = 0;
  for (const caseReport of allCases) {
    try {
      validateResult(caseReport.request, caseReport.result);
    } catch {
      invalidCandidates += 1;
    }
  }
  return {
    parityFailures: allCases.filter(({ parity }) => parity === false).length,
    nondeterministicCases: profileReports.reduce(
      (total, reports) =>
        total + profileNondeterministicCaseCount(reports),
      0,
    ),
    timeouts: allCases.filter(
      ({ result }) => result.status === "timed-out",
    ).length,
    invalidCandidates,
  };
}
