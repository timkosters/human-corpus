# Human corpus eval  2026-11-18T00-01-05

Server: http://127.0.0.1:7861/mcp  Tasks: v1
Baseline: 2026-11-17T23-54-53

## Retrieval

| metric | value | vs baseline |
|---|---|---|
| queries | 36 | = |
| errors | 0 | = |
| results | 360 | = |
| empty_queries | 0 | = |
| latency_cold_p50_s | 0.130 | +0.039 (worse) |
| latency_cold_p95_s | 0.164 | -0.038 (better) |
| latency_cold_max_s | 0.174 | -0.144 (better) |
| latency_warm_p50_s | 0.003 | -0.000 (better) |
| tag_precision | 1.000 | = |
| clean_rate | 0.900 | +0.436 (better) |
| dup_rate | 0.000 | = |
| relevant_at_10 | 0.436 | +0.111 (better) |
| usable_at_10 | 0.672 |  |
| good_at_10 | 0.139 | +0.069 (better) |
| hit_good_at_5 | 0.583 | +0.111 (better) |
| label_coverage | 1.000 | = |
| gutenberg_share | 0.569 | +0.053 (better) |
| flag_rates | dangling_ref 0.044, proper_name 0.033, quote_debris 0.017, dialogue_tag 0.008, quoted 0.003, markup 0.003 | |

## Drafts

| metric | value | vs baseline |
|---|---|---|
| drafts | 8 | = |
| verify_p50_s | 0.024 | -0.613 (better) |
| verify_max_s | 0.035 | -2.745 (better) |
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
| love_letter | 1.000 | 1.000 | 0.567 | 0.300 | 0.163 |
| thank_you_note | 1.000 | 0.867 | 0.567 | 0.267 | 0.164 |
| condolence | 1.000 | 0.900 | 0.300 | 0.133 | 0.124 |
| birthday_toast | 1.000 | 0.933 | 0.567 | 0.100 | 0.153 |
| wedding_speech | 1.000 | 0.833 | 0.467 | 0.100 | 0.174 |
| apology | 1.000 | 1.000 | 0.633 | 0.167 | 0.150 |
| cover_letter | 1.000 | 0.867 | 0.267 | 0.033 | 0.167 |
| retirement_card | 1.000 | 0.833 | 0.367 | 0.067 | 0.151 |
| eulogy | 1.000 | 0.833 | 0.333 | 0.000 | 0.139 |
| congratulations_baby | 1.000 | 0.933 | 0.100 | 0.033 | 0.134 |
| nature_description | 1.000 | 0.867 | 0.767 | 0.333 | 0.155 |
| encouragement | 1.000 | 0.933 | 0.300 | 0.133 | 0.114 |

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
