# Human corpus eval  2026-11-17T22-16-20

Server: https://timourxyz-human-corpus.hf.space/mcp  Tasks: v1
Baseline: none

## Retrieval

| metric | value | vs baseline |
|---|---|---|
| queries | 36 |  |
| errors | 0 |  |
| results | 360 |  |
| empty_queries | 0 |  |
| latency_cold_p50_s | 0.160 |  |
| latency_cold_p95_s | 0.204 |  |
| latency_cold_max_s | 0.256 |  |
| latency_warm_p50_s | 0.117 |  |
| tag_precision | 1.000 |  |
| clean_rate | 0.464 |  |
| dup_rate | 0.000 |  |
| relevant_at_10 | 0.325 |  |
| good_at_10 | 0.069 |  |
| hit_good_at_5 | 0.472 |  |
| label_coverage | 1.000 |  |
| gutenberg_share | 0.517 |  |
| flag_rates | quote_debris 0.306, proper_name 0.158, dangling_ref 0.072, quoted 0.056, dialogue_tag 0.028, archaic 0.006, markup 0.006 | |

## Drafts

| metric | value | vs baseline |
|---|---|---|
| drafts | 8 |  |
| verify_p50_s | 2.989 |  |
| verify_max_s | 21.2 |  |
| strict_human_ratio | 1.000 |  |
| strict_fits_brief | 2.500 |  |
| strict_coherence | 2.750 |  |
| strict_fluency | 2.500 |  |
| strict_voice | 2.000 |  |
| strict_overall | 2.000 |  |
| seeded_human_ratio | 0.161 |  |
| seeded_fits_brief | 4.500 |  |
| seeded_coherence | 4.500 |  |
| seeded_fluency | 4.500 |  |
| seeded_voice | 4.250 |  |
| seeded_overall | 4.500 |  |

## Per task (retrieval)

| task | tag precision | clean | relevant@10 | good@10 | cold s |
|---|---|---|---|---|---|
| love_letter | 1.000 | 0.467 | 0.533 | 0.167 | 0.216 |
| thank_you_note | 1.000 | 0.267 | 0.500 | 0.033 | 0.203 |
| condolence | 1.000 | 0.433 | 0.233 | 0.067 | 0.184 |
| birthday_toast | 1.000 | 0.333 | 0.367 | 0.000 | 0.189 |
| wedding_speech | 1.000 | 0.533 | 0.233 | 0.067 | 0.256 |
| apology | 1.000 | 0.567 | 0.467 | 0.100 | 0.176 |
| cover_letter | 1.000 | 0.567 | 0.100 | 0.033 | 0.201 |
| retirement_card | 1.000 | 0.367 | 0.133 | 0.000 | 0.175 |
| eulogy | 1.000 | 0.433 | 0.333 | 0.000 | 0.204 |
| congratulations_baby | 1.000 | 0.400 | 0.200 | 0.033 | 0.181 |
| nature_description | 1.000 | 0.733 | 0.567 | 0.267 | 0.163 |
| encouragement | 1.000 | 0.467 | 0.233 | 0.067 | 0.151 |

## Drafts

| task | mode | human_ratio | overall | weakness |
|---|---|---|---|---|
| birthday_toast | seeded | 0.000 | 4 | Still short for two minutes; the borrowed toast lines feel a little greeting-card. |
| birthday_toast | strict | 1.000 | 1 | Four disconnected toasts; no story, no humour, nothing about turning forty; far too short for two minutes. |
| condolence | seeded | 0.250 | 5 | Little of it is from the corpus; human_ratio near zero. |
| condolence | strict | 1.000 | 3 | Opens with But, says nothing about the long illness, and the closing question is stiff period phrasing. |
| love_letter | seeded | 0.143 | 4 | Borrowed line about the impatient lover is still a bit ornate next to the plain sentences. |
| love_letter | strict | 1.000 | 2 | Period diction (wing their slow flight, supports me) and an abrupt jump from loneliness to a smile; nothing specific to the couple. |
| thank_you_note | seeded | 0.250 | 5 | Corpus contributed only one phrase; the piece is mostly freshly written. |
| thank_you_note | strict | 1.000 | 2 | Cannot mention the dog or the neighbour; the ellipsis fragment and Victorian debt line read as odd. |
