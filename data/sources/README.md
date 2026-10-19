# Reference sources for the knowledge base

Put one file per work here. `scripts/build_kb.py` loads every `*.txt` and `*.jsonl` file.
Only add text you have permission to use, and record where it came from in `data/sources/SOURCES.csv`.

## Plain-text format (`*.txt`)

```
# source_type: commentary
# work: Nibandhasangraha (Dalhana)
# chapter: 1
# shloka: 3
<Dalhana's comment on verse 3, in Devanagari, copied exactly from the edition>
# shloka: 4
<comment on verse 4>
```

`source_type` must be one of: mula, commentary, kosha, dhatu, grammar, crosstext, gold.
A new `# shloka:` line starts a new chunk; several verses: `# shloka: 21,22`.

## JSON-lines format (`*.jsonl`) — best for lexicons and root lists

```
{"id": "amara.1", "source_type": "kosha", "work": "Amarakosha", "text": "मङ्गलानन्तरारम्भप्रश्नकार्त्स्न्येष्वथो अथ", "ref": "3.3.248"}
{"id": "dhatu.ख्या", "source_type": "dhatu", "work": "Dhatupatha", "text": "ख्या प्रकथने (अदादिः)"}
```

## What to collect (priority order)

| # | Work | source_type | Used by steps |
|---|------|-------------|---------------|
| 1 | Dalhana, Nibandhasangraha on Su. Ni. 1 (NIIMH e-Sushruta shows it) | commentary | 2–7 |
| 2 | Gayadasa, Nyayachandrika on Su. Ni. 1 (where available) | commentary | 3–7 |
| 3 | Amarakosha entries for every word of Ch. 1 | kosha | 2, 4, 6 |
| 4 | Dhatupatha / Dhatu Ratnavali roots used in Ch. 1 | dhatu | 6 |
| 5 | Sandhi, samasa, vibhakti and tantrayukti notes | grammar | 2, 6, 7 |
| 6 | Charaka Ci. 28 & 29, Ashtanga Hridaya Ni. 15 & 16 (parallel passages) | crosstext | 5, 7 |
