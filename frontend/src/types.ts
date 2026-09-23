export type Draft = {city: string | null; event_date: string | null; event_format: string | null; category: string | null; budget_kzt: number | null; duration_hours: number | null; language: string | null; preferences: string};
export type SavedRequest = {id: string; revision: number; draft: Draft};
export type Profile = {id: string; anon_name: string; categories: string[]; city: string; price_from_kzt: number; max_hours: number | null; languages: string[]; event_formats: string[]; description: string; busy_dates: string[]; synthetic: boolean; price_imputed: boolean; city_imputed: boolean};
export type Card = Profile & {explanation: string; badges: string[]; evidence: {quote: string; field: string; matched_features: string[]}; score: {features: number; similarity: number}};
export type Result = {run_id: string; created_at: string; status: 'MATCHED' | 'CATEGORY_ABSENT' | 'NO_MATCH'; message: string; cards: Card[]; eligible_count: number; base_count: number; reasons: {code: string; label: string; count: number}[]; query: Draft; revision: number; catalog_version: string; semantic_version: string; ranking_version: string; signature: string; elapsed_ms: number; warnings: string[]; date_comparison: {previous_date: string; current_date: string; changes: string[]} | null};
export type Alternative = {kind: string; label: string; patch: Partial<Draft>; count: number; candidate_ids: string[]};
export type Message = {role: 'user' | 'assistant'; content: string};
export type Options = {cities: string[]; categories: string[]; event_formats: string[]; languages: string[]; calendar_start: string; calendar_end: string; total: number; city_counts: Record<string, number>; category_counts: Record<string, number>; assistant_mode: string; semantic_mode: string; catalog_version: string};

