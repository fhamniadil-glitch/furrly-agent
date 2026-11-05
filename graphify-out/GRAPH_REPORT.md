# Graph Report - furrly-agent  (2026-11-05)

## Corpus Check
- 9 files · ~6,151 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 1, .csv 1)

## Summary
- 140 nodes · 185 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c9b10772`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- publisher.py
- env
- responder.py
- Mise en route (une seule fois, ~30 min)
- env
- publish.yml
- respond.yml
- collect
- FURRLY : ce que l'agent sait (source : furrlyrex.fr)
- CLAUDE.md

## God Nodes (most connected - your core abstractions)
1. `env` - 14 edges
2. `env` - 9 edges
3. `Mise en route (une seule fois, ~30 min)` - 9 edges
4. `Agent de publication FURRLY` - 8 edges
5. `media_url()` - 7 edges
6. `decide()` - 7 edges
7. `FURRLY : ce que l'agent sait (source : furrlyrex.fr)` - 7 edges
8. `steps` - 6 edges
9. `steps` - 6 edges
10. `gget()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Ajouter des posts` --references--> `media_url()`  [INFERRED]
  README.md → publisher.py
- `Bon à savoir` --references--> `media_url()`  [INFERRED]
  README.md → publisher.py

## Import Cycles
- None detected.

## Communities (10 total, 1 thin omitted)

### Community 0 - "publisher.py"
Cohesion: 0.15
Nodes (10): is_due(), load_state(), main(), media_url(), post_facebook(), post_instagram(), post_tiktok(), save_state() (+2 more)

### Community 1 - "env"
Cohesion: 0.10
Nodes (20): DRY_RUN, FB_PAGE_ID, FB_PAGE_TOKEN, IG_TOKEN, IG_USER_ID, MEDIA_BASE_URL, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET (+12 more)

### Community 2 - "responder.py"
Cohesion: 0.21
Nodes (13): act_comment(), act_message(), ask_claude(), ask_gemini(), build_prompt(), decide(), gpost(), knowledge() (+5 more)

### Community 3 - "Mise en route (une seule fois, ~30 min)"
Cohesion: 0.11
Nodes (17): 1. Créer le dépôt GitHub, 2. Ajouter les visuels dans `media/`, 3. Dire à l'agent où sont tes visuels, 4. Obtenir tes clés Meta (Facebook + Instagram), 5. Enregistrer les clés (en secret), 6. Tester sans risque, 7. ⚠️ Éviter les doublons avec Metricool, 8. Passer en réel (+9 more)

### Community 4 - "env"
Cohesion: 0.13
Nodes (15): ANTHROPIC_API_KEY, FB_PAGE_ID, FB_PAGE_TOKEN, GEMINI_API_KEY, IG_TOKEN, IG_USER_ID, REPONSES_DRY_RUN, REPONSES_SCOPE (+7 more)

### Community 5 - "publish.yml"
Cohesion: 0.14
Nodes (13): concurrency, cancel-in-progress, group, jobs, publish, name, on, schedule (+5 more)

### Community 6 - "respond.yml"
Cohesion: 0.14
Nodes (13): concurrency, cancel-in-progress, group, jobs, respond, name, on, schedule (+5 more)

### Community 7 - "collect"
Cohesion: 0.31
Nodes (7): collect(), ig(), conversations(), fb_comments(), gget(), ig_comments(), recent()

### Community 8 - "FURRLY : ce que l'agent sait (source : furrlyrex.fr)"
Cohesion: 0.25
Nodes (7): Catalogue (prix TTC), Contact (pour tout ce qui concerne une commande précise), FURRLY : ce que l'agent sait (source : furrlyrex.fr), La marque, Livraison, Offres permanentes (appliquées automatiquement au panier, pas de code à saisir), Retours et remboursement

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `media_url()` connect `publisher.py` to `Mise en route (une seule fois, ~30 min)`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Should `publisher.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14736842105263157 - nodes in this community are weakly interconnected._
- **Why does `Agent de publication FURRLY` connect `Mise en route (une seule fois, ~30 min)` to `publisher.py`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Should `env` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Mise en route (une seule fois, ~30 min)` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `env` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `publish.yml` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._