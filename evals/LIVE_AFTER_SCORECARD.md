# Human corpus eval  2026-11-18T00-51-37

Server: https://timourxyz-human-corpus.hf.space/mcp  Tasks: v1
Baseline: 2026-11-17T22-16-20

## Retrieval

| metric | value | vs baseline |
|---|---|---|
| queries | 36 | = |
| errors | 0 | = |
| results | 360 | = |
| empty_queries | 0 | = |
| latency_cold_p50_s | 0.249 | +0.089 (worse) |
| latency_cold_p95_s | 0.343 | +0.139 (worse) |
| latency_cold_max_s | 1.061 | +0.806 (worse) |
| latency_warm_p50_s | 0.112 | -0.004 (better) |
| tag_precision | 1.000 | = |
| clean_rate | 0.889 | +0.425 (better) |
| dup_rate | 0.000 | = |
| relevant_at_10 | 0.441 | +0.116 (better) |
| usable_at_10 | 0.671 |  |
| good_at_10 | 0.137 | +0.068 (better) |
| hit_good_at_5 | 0.583 | +0.111 (better) |
| label_coverage | 0.989 | -0.011 (worse) |
| gutenberg_share | 0.567 | +0.050 (better) |
| flag_rates | dangling_ref 0.044, proper_name 0.042, quote_debris 0.017, dialogue_tag 0.008, quoted 0.003, markup 0.003, archaic 0.003 | |

## Drafts

| metric | value | vs baseline |
|---|---|---|
| drafts | 8 | = |
| verify_p50_s | 0.127 | -2.862 (better) |
| verify_max_s | 0.140 | -21.062 (better) |
| strict_human_ratio | 1.000 | = |
| strict_fits_brief | 3.750 | +1.250 (better) |
| strict_coherence | 3.500 | +0.750 (better) |
| strict_fluency | 3.250 | +0.750 (better) |
| strict_voice | 3.250 | +1.250 (better) |
| strict_overall | 3.500 | +1.500 (better) |
| seeded_human_ratio | 0.161 | = |
| seeded_fits_brief | 4.500 | = |
| seeded_coherence | 4.500 | = |
| seeded_fluency | 4.500 | = |
| seeded_voice | 4.250 | = |
| seeded_overall | 4.500 | = |

## Per task (retrieval)

| task | tag precision | clean | relevant@10 | good@10 | cold s |
|---|---|---|---|---|---|
| love_letter | 1.000 | 0.967 | 0.626 | 0.311 | 0.367 |
| thank_you_note | 1.000 | 0.833 | 0.537 | 0.200 | 0.343 |
| condolence | 1.000 | 0.900 | 0.300 | 0.133 | 0.294 |
| birthday_toast | 1.000 | 0.900 | 0.567 | 0.100 | 0.303 |
| wedding_speech | 1.000 | 0.800 | 0.500 | 0.133 | 0.327 |
| apology | 1.000 | 1.000 | 0.626 | 0.170 | 0.253 |
| cover_letter | 1.000 | 0.867 | 0.274 | 0.033 | 0.277 |
| retirement_card | 1.000 | 0.867 | 0.367 | 0.067 | 0.283 |
| eulogy | 1.000 | 0.833 | 0.333 | 0.000 | 1.061 |
| congratulations_baby | 1.000 | 0.933 | 0.100 | 0.033 | 0.276 |
| nature_description | 1.000 | 0.867 | 0.733 | 0.333 | 0.254 |
| encouragement | 1.000 | 0.900 | 0.333 | 0.133 | 0.228 |

## Drafts

| task | mode | human_ratio | overall | weakness |
|---|---|---|---|---|
| birthday_toast | seeded | 0.000 | 4 | Still short for two minutes; the borrowed toast lines feel a little greeting-card. |
| birthday_toast | strict | 1.000 | 3 | Warm and on occasion, but still a string of toasts with no story, nothing about forty, and too short for two minutes. |
| condolence | seeded | 0.250 | 5 | Little of it is from the corpus; human_ratio near zero. |
| condolence | strict | 1.000 | 4 | subjected to such a sorrow is stiff, and nothing acknowledges the long illness. |
| love_letter | seeded | 0.143 | 4 | Borrowed line about the impatient lover is still a bit ornate next to the plain sentences. |
| love_letter | strict | 1.000 | 4 | The run-on dream sentence is a little clumsy, but it reads as one person missing a partner who is away. |
| thank_you_note | seeded | 0.250 | 5 | Corpus contributed only one phrase; the piece is mostly freshly written. |
| thank_you_note | strict | 1.000 | 3 | Names the dog but not the hospital stay; So we were in good hands is a slightly odd bridge and the last line is formal. |
