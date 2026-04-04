"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  DEFAULT_MATCH_FILTERS,
  EXPERIENCE_YEAR_OPTIONS,
  getMatchFilterSummary,
  INTERNSHIP_OPTIONS,
  normalizeMatchFilters,
  POST_TIME_OPTIONS,
  ROLE_CATEGORY_OPTIONS,
  WORK_MODE_OPTIONS,
} from "@/lib/match-filters";
import type { MatchFilters, WorkMode } from "@/types/domain";

type MatchFilterFormProps = {
  initialFilters: MatchFilters;
  submitLabel: string;
  onSubmit: (filters: MatchFilters) => void;
  isSubmitting?: boolean;
  onCancel?: () => void;
  cancelLabel?: string;
  onReset?: () => void;
};

export function MatchFilterForm({
  initialFilters,
  submitLabel,
  onSubmit,
  isSubmitting = false,
  onCancel,
  cancelLabel,
  onReset,
}: MatchFilterFormProps) {
  const [filters, setFilters] = useState<MatchFilters>(normalizeMatchFilters(initialFilters));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFilters(normalizeMatchFilters(initialFilters));
    setError(null);
  }, [initialFilters]);

  const summary = getMatchFilterSummary(filters);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = normalizeMatchFilters(filters);
    if (
      normalized.minExperienceYears != null &&
      normalized.maxExperienceYears != null &&
      normalized.maxExperienceYears < normalized.minExperienceYears
    ) {
      setError("工作经验上限不能小于下限。");
      return;
    }
    setError(null);
    onSubmit(normalized);
  }

  function handleRoleToggle(value: string) {
    setFilters((current) => ({
      ...current,
      roleCategories: toggleValue(current.roleCategories, value),
    }));
  }

  function handleWorkModeToggle(value: WorkMode) {
    setFilters((current) => ({
      ...current,
      workModes: toggleValue(current.workModes, value) as WorkMode[],
    }));
  }

  function handleReset() {
    setFilters(DEFAULT_MATCH_FILTERS);
    setError(null);
    onReset?.();
  }

  return (
    <form className="filter-form" onSubmit={handleSubmit}>
      <div className="filter-grid">
        <section className="filter-section">
          <div className="filter-section-header">
            <h3>岗位方向</h3>
            <p>可多选，优先匹配这些岗位类型。</p>
          </div>
          <div className="filter-chip-grid">
            {ROLE_CATEGORY_OPTIONS.map((option) => {
              const active = filters.roleCategories.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  className={active ? "filter-chip filter-chip-active" : "filter-chip"}
                  aria-pressed={active}
                  onClick={() => handleRoleToggle(option.value)}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </section>

        <section className="filter-section">
          <div className="filter-section-header">
            <h3>工作方式</h3>
            <p>远程、混合办公和现场坐班可同时选择。</p>
          </div>
          <div className="filter-chip-grid">
            {WORK_MODE_OPTIONS.map((option) => {
              const active = filters.workModes.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  className={active ? "filter-chip filter-chip-active" : "filter-chip"}
                  aria-pressed={active}
                  onClick={() => handleWorkModeToggle(option.value)}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </section>

        <section className="filter-section filter-section-compact">
          <div className="filter-section-header">
            <h3>基础要求</h3>
            <p>控制是否实习、发布时间和经验年限。</p>
          </div>
          <div className="filter-field-grid">
            <label className="filter-field">
              <span>是否实习</span>
              <select
                className="field-input filter-select"
                value={filters.internshipPreference}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    internshipPreference: event.target.value as MatchFilters["internshipPreference"],
                  }))
                }
              >
                {INTERNSHIP_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="filter-field">
              <span>发布时间</span>
              <select
                className="field-input filter-select"
                value={filters.postedWithinDays != null ? String(filters.postedWithinDays) : ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    postedWithinDays: event.target.value ? Number(event.target.value) : null,
                  }))
                }
              >
                {POST_TIME_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="filter-field">
              <span>经验下限</span>
              <select
                className="field-input filter-select"
                value={filters.minExperienceYears != null ? String(filters.minExperienceYears) : ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    minExperienceYears: event.target.value ? Number(event.target.value) : null,
                  }))
                }
              >
                {EXPERIENCE_YEAR_OPTIONS.map((option) => (
                  <option key={`min-${option.value || "all"}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="filter-field">
              <span>经验上限</span>
              <select
                className="field-input filter-select"
                value={filters.maxExperienceYears != null ? String(filters.maxExperienceYears) : ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    maxExperienceYears: event.target.value ? Number(event.target.value) : null,
                  }))
                }
              >
                {EXPERIENCE_YEAR_OPTIONS.map((option) => (
                  <option key={`max-${option.value || "all"}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
      </div>

      <div className="filter-summary-row">
        <div>
          <p className="filter-summary-label">当前筛选</p>
          {summary.length > 0 ? (
            <div className="job-chip-row">
              {summary.map((item) => (
                <span key={item} className="tag">
                  {item}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">当前未设置额外筛选，将返回全部可匹配岗位。</p>
          )}
        </div>
      </div>

      {error ? <p className="status-message status-error">{error}</p> : null}

      <div className="filter-actions">
        <button type="submit" className="button-primary" disabled={isSubmitting}>
          {isSubmitting ? "处理中..." : submitLabel}
        </button>
        <button type="button" className="button-secondary" onClick={handleReset} disabled={isSubmitting}>
          重置条件
        </button>
        {onCancel ? (
          <button type="button" className="button-ghost" onClick={onCancel} disabled={isSubmitting}>
            {cancelLabel ?? "取消"}
          </button>
        ) : null}
      </div>
    </form>
  );
}

function toggleValue(values: readonly string[], target: string): string[] {
  return values.includes(target) ? values.filter((value) => value !== target) : [...values, target];
}
