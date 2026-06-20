"""ADR-760 Layer 3 verification — Browse page UX cleanup.

This is a manual verification harness, not an automated test suite.
CI cannot run it because the checks require a real browser at 1440x900
and 375x812 (rule #28 + rule #34: HTTP 200 from curl is NOT proof a
dashboard page works; mechanical pass is not value).

The Augur agent runs this via Chrome MCP / Playwright as part of
`/adr implement ADR-760` Task 11.

# BASELINE 2026-05-16 (measured before any code change, using the
# imprecise `main .grid > div` selector that conflated the search toolbar
# and the cards grid):
#   desktop_1440x900_cards_above_fold     = 7   (selector counted toolbar grid)
#   desktop_1440x900_first_card_top_px    = 416 (was actually the toolbar's top, not the cards')
#   desktop_1440x900_headings_in_main     = 1
#   mobile_375x812_first_card_top_px      = 601 (also off by ~50px for same reason)

# PRECISE POST-CHANGE 2026-05-16 (after commits 8ba5390cb + 1a0295b1a
# + 08a2dbf74 + <followup>, using the corrected selector that targets
# only the cards grid):
#   desktop_1440x900_cards_above_fold     = 9    (was 6 mid-stream)  -- MET (>= 9)
#   desktop_1440x900_cards_fully_visible  = 6    (2 complete rows)
#   desktop_1440x900_first_card_top_px    = 349
#   desktop_1440x900_headings_in_main     = 31   (1 H1 + 30 card H3s)  -- MET
#   desktop_1440x900_h1_text              = "Browse · Skills"          -- MET
#   stats_disclosure                      = present, closed by default, persists -- MET
#   manage_button_label                   = "Manage"                   -- MET
#   welcome_banner_present                = false                      -- MET (removed by ADR-760)
#   mobile_375x812_first_card_top_px      = 647 (was estimated 601 in baseline) -- MISS vs target 350
#   console_errors                        = 0                          -- MET

# MOBILE FOLLOW-UP 2026-05-17:
#   mobile_375x812_first_card_top_px      = 339 -- MET (<= 350)
#   mobile_375x812_cards_above_fold       = 2
#   mobile_375x812_cards_fully_visible    = 1
#   desktop_1440x900_cards_above_fold     = 9   -- still MET
#   desktop_1440x900_cards_fully_visible  = 6   -- still MET
#   console_errors                        = 0
#
#   The mobile fix uses a native category select in place of the grouped
#   OverflowBar below md, and keeps the desktop grouped OverflowBar intact.
#   Mobile search keeps the primary search field and Filters trigger on one
#   row; search mode and sort remain available inside the mobile filter panel.

# QUALITATIVE WINS (real, shipped):
#   - Screen-reader heading hierarchy restored: every card has a real <h3>
#   - H1 carries active category context ("Browse · Skills")
#   - WelcomeBanner removed entirely from /browse (Brain and Settings are
#     1-click from the sidebar already; the banner was redundant chrome)
#   - Inventory stats moved behind opt-in disclosure (localStorage-persisted)
#   - tabular-nums on count spans (no digit jitter on filter change)
#   - "Manage" replaces opaque "Actions" label
#   - OverflowBar journey-group labels now render inline before each cluster
#     (saves ~24px of vertical chrome vs the previous header-row pattern)
#   - NoteQueueItem failed URL ingests get a Retry button
#   - Splitter announces "N% width" to SR; skeleton respects prefers-reduced-motion
#   - Description text demoted to text-xs text-muted on a single line
#   - Summary panel padding tightened (p-4/md:p-5 -> p-3/md:p-4)
#   - Toolbar wrapper padding tightened (p-4 -> p-3)

# Verification recipe (run from Chrome MCP / Playwright at each viewport):
#
#   const allGrids = Array.from(document.querySelectorAll('main .grid'));
#   const cardsGrid = allGrids.find(g =>
#     g.className.includes('lg:grid-cols-3') ||
#     g.className.includes('md:grid-cols-2')
#   );
#   const cards = Array.from(cardsGrid.children);
#   const above = cards.filter(c => {
#     const r = c.getBoundingClientRect();
#     return r.top < window.innerHeight && r.bottom > 0;
#   });
#   const fully = cards.filter(c => {
#     const r = c.getBoundingClientRect();
#     return r.top >= 0 && r.bottom <= window.innerHeight;
#   });
#   ({
#     cards_above_fold: above.length,
#     cards_fully_visible: fully.length,
#     first_card_top: Math.round(cards[0].getBoundingClientRect().top),
#   })
"""
