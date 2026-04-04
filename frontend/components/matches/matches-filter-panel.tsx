"use client";

import { useRouter } from "next/navigation";

import { MatchFilterForm } from "@/components/matches/match-filter-form";
import { appendMatchFiltersToSearchParams, hasActiveMatchFilters } from "@/lib/match-filters";
import { logFrontendEvent } from "@/lib/logger";
import type { MatchFilters } from "@/types/domain";

type MatchesFilterPanelProps = {
  resumeId?: string;
  currentPage: number;
  filters: MatchFilters;
};

export function MatchesFilterPanel({ resumeId, currentPage, filters }: MatchesFilterPanelProps) {
  const router = useRouter();

  function handleApply(nextFilters: MatchFilters) {
    const params = new URLSearchParams();
    if (resumeId) {
      params.set("resumeId", resumeId);
    }
    appendMatchFiltersToSearchParams(params, nextFilters);
    const query = params.toString();
    router.push(query ? `/matches?${query}` : "/matches");
    router.refresh();
    logFrontendEvent("matches.filters.applied", {
      resumeId: resumeId ?? null,
      previousPage: currentPage,
      hasActiveFilters: hasActiveMatchFilters(nextFilters),
      filters: nextFilters,
    });
  }

  function handleReset() {
    logFrontendEvent("matches.filters.reset", {
      resumeId: resumeId ?? null,
      previousPage: currentPage,
    });
  }

  return (
    <div className="filter-panel">
      <MatchFilterForm
        initialFilters={filters}
        submitLabel="重新匹配岗位"
        onSubmit={handleApply}
        onReset={handleReset}
      />
    </div>
  );
}
