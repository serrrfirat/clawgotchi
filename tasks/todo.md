# Curiosity-Driven Selective Feature Building

## Tasks

- [x] Replace keyword matching with relevance scoring in `moltbook_client.py`
  - Added `RELEVANCE_CATEGORIES` (5 categories with weighted scoring)
  - Added `NOISE_SIGNALS` (spam/fiction detection)
  - Added `score_post_relevance()` function
  - Rewrote `extract_feature_ideas()` to use scoring (threshold >= 0.15, 2+ categories, no noise)

- [x] Rewrite autonomous agent decision and curiosity systems in `autonomous_agent.py`
  - `CuriosityQueue.add()` now tracks `seen_count`, `sources`, `categories`; deduplicates by boosting existing items
  - Added `CuriosityQueue.get_mature()` — requires seen_count >= 2 OR age >= 12 hours
  - Rewrote `_decide_next_action()` — REST is default, BUILD only on mature + taste-checked items
  - Rewrote `_explore_curiosity()` as intake funnel — scores posts, rejects ~90%, feeds curiosity queue
  - Added `_taste_check()` — checks ideas against TasteProfile rejection history
  - Added `TEMPLATE_CATEGORIES` — category-specific templates for feature building
  - Fixed `_classify_idea()` NoneType crash — now uses category data with keyword fallback
  - Re-enabled `_build_cli()` and `_build_skill()` with gating (writes files, no auto-commit)

- [x] Run tests and verify scoring behavior
  - All 282 tests pass
  - Scoring verified: multi-category posts score high, spam scores 0 with noise flag
  - Maturation verified: items need seen_count >= 2 or age >= 12h
  - Action distribution over 30 cycles: REST 40%, VERIFY 33%, EXPLORE 13%, CURATE 13%, BUILD 0% (needs mature items)

## Review

All changes implemented and verified. Two files modified:
- `moltbook_client.py` — relevance scoring replaces keyword matching
- `autonomous_agent.py` — curiosity maturation, selective building, taste integration
