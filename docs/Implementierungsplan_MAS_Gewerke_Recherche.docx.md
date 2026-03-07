

**IMPLEMENTIERUNGSPLAN**

LLM-basiertes Multi-Agenten-System

Gewerkespezifische Publikationsrecherche

Version 1.0  •  März 2026

Pydantic-AI  •  OpenAlex  •  Semantic Scholar  •  CORE

# **Inhaltsverzeichnis**

# **1\. Executive Summary**

Dieses Dokument beschreibt den vollständigen Implementierungsplan für ein LLM-basiertes Multi-Agenten-System (MAS), das autonom wissenschaftliche Publikationen für spezifische deutsche Handwerksgewerke recherchiert, extrahiert, evaluiert und als validierte Dossiers publiziert.

Das System basiert auf dem Orchestrator-Worker-Pattern mit fünf spezialisierten Agenten, implementiert in Pydantic-AI mit typsicherer Datenvalidierung. Es nutzt eine föderierte Retrieval-Strategie über OpenAlex, Semantic Scholar und CORE mit SPECTER2-Re-Ranking, und sichert die Ausgabequalität durch einen tool-basierten Evaluator-Optimizer-Loop mit maximal zwei Iterationen.

| Kern-Design-Prinzipien Typsicherheit durch Pydantic-Modelle an jeder Agenten-Schnittstelle • Externe Verifikation statt LLM-Selbstkorrektur • Bilinguale Query-Expansion (DE/EN) • Parallelisierte Extraktion mit Fan-Out • Deterministische Reproduzierbarkeit durch JSON-Profile als Startpunkt |
| :---- |

# **2\. Systemarchitektur**

## **2.1 Pipeline-Übersicht**

Das System durchläuft fünf sequenzielle Phasen, wobei Phase 3 (Extraktion) massiv parallelisiert wird:

| Phase | Bezeichnung | Agenten | Parallelität |
| :---- | :---- | :---- | :---- |
| 0 | Deterministic Input | Keiner (statisches JSON) | n/a |
| 1 | Themenidentifikation | Profile Parser \+ Orchestrator | Sequenziell |
| 2 | Föderiertes Retrieval | Search Agent \+ Result Merger | Pro Query parallel |
| 3 | Kontext-Extraktion | n × Data Extraction Agents | Massiv parallel (Fan-Out) |
| 4 | Evaluation | Evaluator/Critic Agent | Sequenziell, max 2 Iterationen |
| 5 | Publikation | Publisher Agent | Sequenziell |

## **2.2 Technologie-Stack**

| Komponente | Technologie | Begründung |
| :---- | :---- | :---- |
| Orchestrierung | Pydantic-AI \+ pydantic-graph | Typsichere Outputs, Dependency Injection, FSM für Workflow |
| LLM (Extraktion) | Claude Sonnet 4.5 / GPT-4o | Kosten-Performance-Balance für parallele Extraktion |
| LLM (Evaluation) | Anderes Modell als Extraktion | Cross-Model-Evaluation gegen Self-Enhancement-Bias |
| Primäre API | OpenAlex REST API | 271M Works, CC0, Keyword \+ Semantic Search |
| Re-Ranking | Semantic Scholar \+ SPECTER2 | Wissenschaftsspezifische Embeddings, kostenlos |
| Volltext-Zugang | CORE API | 46M Open-Access-Volltexte |
| Observability | Logfire | Native Pydantic-AI-Integration, Full-Stack-Tracing |
| Laufzeit | Python 3.12+ / asyncio | Async für parallele Fan-Out-Extraktion |
| Datenvalidierung | Pydantic v2 BaseModel | Schema-Enforcement an jeder Schnittstelle |

# **3\. Agenten-Spezifikationen**

## **3.1 Profile Parsing Agent**

**Hierarchie:** Worker  |  **Phase:** 1  |  **LLM-Nutzung:** Keine (deterministisch)

**Kernaufgabe:** Einlesen, Validieren und Normalisieren des statischen JSON-Gewerks-Profils in ein typsicheres Pydantic-Modell. Kein LLM-Aufruf – rein regelbasierte Transformation.

| Eigenschaft | Spezifikation |
| :---- | :---- |
| Input | Rohes JSON-Gewerks-Profil (Datei oder API-Payload) |
| Output (Pydantic) | GewerksProfilModel (validiert, normalisiert) |
| Fehlerbehandlung | Pydantic ValidationError mit detaillierten Feldfehlern |
| Tools | Keine – reine Pydantic-Validierung |
| Abhängigkeiten | JSON-Schema-Definition, Gewerke-Taxonomie (HWO Anlage A/B1/B2) |

### **Pydantic-Modell: GewerksProfilModel**

Das zentrale Datenmodell validiert alle Felder des Gewerks-Profils:

| Feld | Typ | Beschreibung | Beispiel |
| :---- | :---- | :---- | :---- |
| gewerk\_id | str | Eindeutige ID nach HWO | "A\_01\_MAURER" |
| gewerk\_name | str | Offizieller Name | "Maurer und Betonbauer" |
| hwo\_anlage | Literal\['A','B1','B2'\] | Regulatorische Stufe | "A" |
| kernkompetenzen | list\[str\] | Kernkompetenzen | \["Mauerwerksbau", ...\] |
| taetigkeitsfelder | dict\[str, list\[str\]\] | Unterteilt nach Bereichen | {"Herstellung": \[...\]} |
| techniken\_manuell | list\[str\] | Manuelle Techniken | \["Stemmen", "Verzapfen"\] |
| techniken\_maschinell | list\[str\] | Maschinelle Techniken | \["CNC-Bearbeitung"\] |
| techniken\_oberflaeche | list\[str\] | Oberflächentechniken | \["Lasieren", "Beizen"\] |
| werkstoffe | list\[str\] | Materialien/Werkstoffe | \["Massivholz", "Beton"\] |
| software\_tools | list\[str\] | Digitale Werkzeuge | \["AutoCAD", "BIM"\] |
| arbeitsbedingungen | list\[str\] | Ergonomie-Parameter | \["Schwere körp. Arbeit"\] |

## **3.2 Orchestrator / Planner Agent**

**Hierarchie:** Management  |  **Phase:** 1  |  **LLM-Nutzung:** Ja (Tree of Thoughts)

**Kernaufgabe:** Generierung hochspezifischer Forschungsfragen und Suchstrategien aus dem validierten Gewerks-Profil. Bilinguale Query-Expansion (DE \+ EN). Steuerung des gesamten Pipeline-Flusses via Programmatic Hand-offs.

| Eigenschaft | Spezifikation |
| :---- | :---- |
| Input | GewerksProfilModel via RunContext (deps) |
| Output (Pydantic) | SearchStrategyModel (Forschungsfragen \+ Query-Sets) |
| LLM-Strategie | Tree of Thoughts (ToT) mit automatischem Backtracking |
| Tools | Keine externen – nutzt LLM-Reasoning \+ Profildaten |
| Prompt-Technik | ToT: Generiere 3 Gedankenbäume → Bewerte Relevanz vs. Profil → Prune irrelevante Äste |
| Hand-off | Programmatic Hand-off an Search Agent nach Validierung |
| Kognitive Entlastung | Keine Evaluierung oder Synthese – nur Planung und Delegation |

### **Pydantic-Modell: SearchStrategyModel**

| Feld | Typ | Beschreibung |
| :---- | :---- | :---- |
| gewerk\_id | str | Referenz zum Quell-Profil |
| forschungsfragen | list\[ForschungsFrage\] | 3–10 spezifische Forschungsfragen |
| keyword\_queries\_de | list\[str\] | Deutsche Keyword-Queries mit Bool-Operatoren |
| keyword\_queries\_en | list\[str\] | Englische Keyword-Queries mit Bool-Operatoren |
| semantic\_queries\_en | list\[str\] | Englische Absatz-Descriptions für Semantic Search |
| hyde\_abstracts | list\[str\] | Hypothetische Abstracts für HyDE-Retrieval |
| concept\_filter\_ids | list\[str\] | None | OpenAlex Concept-IDs zur Eingrenzung |
| max\_results\_per\_query | int | Zielanzahl Ergebnisse pro Query (Default: 50\) |

## **3.3 OpenAlex Search Agent**

**Hierarchie:** Worker  |  **Phase:** 2  |  **LLM-Nutzung:** Minimal (Query-Reformulierung bei Nulltreffern)

**Kernaufgabe:** Ausführung der Suchstrategie über drei föderierte APIs (OpenAlex, Semantic Scholar, CORE). Deduplizierung und SPECTER2-basiertes Re-Ranking der Ergebnisse.

| Eigenschaft | Spezifikation |
| :---- | :---- |
| Input | SearchStrategyModel via Programmatic Hand-off |
| Output (Pydantic) | RetrievalResultModel (deduplizierte, gerankte Publikationsliste) |
| Primäre API | OpenAlex /works (?search=, ?search.semantic=, Filter) |
| Sekundäre APIs | Semantic Scholar /paper/search, CORE /search/works |
| Fehlerbehandlung | Automatische Query-Reformulierung bei \<5 Ergebnissen |
| Rate Limits | OpenAlex: 10 req/s (polite pool) | S2: 5000/5min | CORE: 5/10s |
| Kosten-Awareness | OA Keyword: $0.0001/req | OA Semantic: $0.001/req | S2/CORE: kostenlos |

### **Tools des Search Agent**

| Tool-Name | API | Parameter | Rückgabe |
| :---- | :---- | :---- | :---- |
| search\_openalex\_keyword | OpenAlex /works | query: str, filters: dict, per\_page: int | list\[OpenAlexWork\] |
| search\_openalex\_semantic | OpenAlex /works | semantic\_query: str, filters: dict | list\[OpenAlexWork\] |
| search\_semantic\_scholar | S2 /paper/search | query: str, fields: list\[str\], limit: int | list\[S2Paper\] |
| search\_core | CORE /search/works | query: str, limit: int | list\[CoreWork\] |
| get\_specter2\_embeddings | S2 /paper/batch | paper\_ids: list\[str\] | dict\[str, list\[float\]\] |
| find\_similar\_openalex | OA /works (seed) | seed\_work\_id: str | list\[OpenAlexWork\] |
| merge\_and\_rerank | Intern | results: list\[UnifiedPaper\], query\_embedding: list\[float\] | list\[RankedPaper\] |

### **Retrieval-Pipeline im Detail**

1. **Keyword Search (DE \+ EN):** Parallele Ausführung aller keyword\_queries\_de und keyword\_queries\_en über OpenAlex ?search= mit .no\_stem für Fachbegriffe.

2. **Semantic Search (EN):** semantic\_queries\_en und hyde\_abstracts über OpenAlex ?search.semantic= und Semantic Scholar.

3. **CORE Volltext-Suche:** Parallele Suche für Queries mit hoher Volltext-Relevanz (z.B. Normen, Verfahrensbeschreibungen).

4. **DOI-Deduplizierung:** Exakter DOI-Match → Normalisierter Titel \+ Erstautor \+ Jahr (Jaro-Winkler \>0.95) → Embedding-Similarity für Grenzfälle.

5. **SPECTER2 Re-Ranking:** Batch-Abruf der SPECTER2-Embeddings via Semantic Scholar. Cosine-Similarity zum Gewerks-Profil-Embedding. Reciprocal Rank Fusion (RRF) über alle Quellen.

6. **Top-k Selektion:** Die besten k Publikationen (Default: 30\) werden als RankedPaper-Liste an Phase 3 übergeben.

## **3.4 Data Extraction Agent (Fan-Out)**

**Hierarchie:** Worker  |  **Phase:** 3  |  **LLM-Nutzung:** Ja (pro Paper eine Instanz)

**Kernaufgabe:** Parallelisierte Extraktion relevanter Informationen aus einzelnen Publikationen in strukturierte Einzeldossiers. Jede Instanz arbeitet isoliert an einem Paper, um das Lost-in-the-Middle-Problem zu vermeiden.

| Fan-Out-Architektur Für jedes der Top-k Papers wird via asyncio.gather() eine separate Agent-Instanz gestartet. Jede Instanz erhält genau ein Paper (Abstract \+ ggf. Volltext via CORE) und das GewerksProfilModel als RunContext. Die Instanzen laufen vollständig parallel und unabhängig. |
| :---- |

| Eigenschaft | Spezifikation |
| :---- | :---- |
| Input | Einzelnes RankedPaper \+ GewerksProfilModel via RunContext |
| Output (Pydantic) | PublikationsDossierModel (strukturiertes Einzeldossier) |
| LLM-Instanzen | n parallele Instanzen (eine pro Paper, Default n=30) |
| Kontextfenster | Isoliert: nur 1 Paper pro Instanz (kein Cross-Paper-Rauschen) |
| Extraktion | Kernaussage, Methodik, Relevanz, Schlüsselzahlen, Limitationen |
| Concurrency | asyncio.gather() mit Semaphore (max 10 gleichzeitig) |
| Token-Budget | \~2000 Output-Tokens pro Dossier via UsageLimits |

### **Pydantic-Modell: PublikationsDossierModel**

| Feld | Typ | Beschreibung |
| :---- | :---- | :---- |
| paper\_id | str | DOI oder OpenAlex-ID |
| titel | str | Originaltitel der Publikation |
| autoren | list\[str\] | Erstautor \+ et al. |
| jahr | int | Publikationsjahr |
| quelle | str | Journal/Konferenz |
| kernaussage | str | Zentrale Erkenntnis (2–4 Sätze) |
| methodik | str | Angewandte Forschungsmethodik |
| methodik\_validiert | bool | Ist Methodik schlüssig beschrieben? |
| relevanz\_fuer\_gewerk | str | Konkreter Bezug zum Gewerks-Profil |
| relevanz\_score | float (0–1) | Quantifizierte Relevanz |
| schluesselzahlen | list\[str\] | Extrahierte Metriken/Statistiken |
| limitationen | str | Einschränkungen der Studie |
| volltext\_verfuegbar | bool | Wurde Volltext oder nur Abstract genutzt? |
| quell\_passage | str | Exakte Passage für spätere NLI-Verifikation |

## **3.5 Evaluator / Critic Agent**

**Hierarchie:** Worker  |  **Phase:** 4  |  **LLM-Nutzung:** Ja (anderes Modell als Extraktion)

**Kernaufgabe:** Qualitätskontrolle aller Einzeldossiers durch Cross-Evaluation, tool-basierte externe Verifikation und inhaltliche Deduplizierung. Nutzt ein anderes LLM-Modell als der Extraction Agent, um Self-Enhancement-Bias zu vermeiden.

| Kritisches Design-Prinzip: Externe Verifikation statt Selbstkorrektur Huang et al. (ICLR 2024\) zeigten, dass LLMs ohne externe Feedback-Signale ihre eigenen Fehler nicht zuverlässig korrigieren können. Der Evaluator nutzt daher drei tool-basierte Verifikationsmechanismen als harte Gates, nicht LLM-Urteil allein. |
| :---- |

### **Verifikations-Tools**

| Tool | Mechanismus | Prüfung | Gate-Typ |
| :---- | :---- | :---- | :---- |
| doi\_crossref\_check | Crossref API Singleton-Lookup | Existiert die zitierte Publikation? Stimmen Metadaten? | Hard Gate |
| source\_passage\_nli | NLI-Modell (z.B. DeBERTa-v3) | Ist die Kernaussage durch die quell\_passage gestützt? | Hard Gate |
| numeric\_cross\_check | Regelbasiert \+ LLM | Stimmen extrahierte Zahlen mit der Quelle überein? | Soft Gate |
| profil\_relevanz\_check | Cosine Similarity | Embedding-Ähnlichkeit Dossier ↔ Gewerks-Profil \> Threshold | Soft Gate |

### **Evaluator-Optimizer-Loop**

Der Evaluator durchläuft folgenden Algorithmus:

1. **Batch-Prüfung:** Alle Dossiers werden parallel durch die vier Verifikations-Tools geschleust.

2. **Binäre Entscheidung pro Dossier:** Jedes Tool gibt PASS/FAIL zurück. Hard-Gate-Failures führen zum sofortigen Ausschluss.

3. **Deduplizierung:** Paarweise Embedding-Similarity aller Kernaussagen. Bei Cosine \>0.92: Verschmelzung des schwächeren Dossiers.

4. **Feedback-Loop (max 2 Iterationen):** Dossiers mit Soft-Gate-Failures erhalten textuelle Kritik und werden an den Extraction Agent zurückdelegiert. Frühzeitiger Abbruch bei Konvergenz (Feedback ändert sich nicht mehr substantiell).

5. **Freigabe:** Verbleibende Dossiers erhalten quality\_approved=True und werden via Programmatic Hand-off an den Publisher übergeben.

### **Pydantic-Modell: EvaluationResultModel**

| Feld | Typ | Beschreibung |
| :---- | :---- | :---- |
| dossier\_id | str | Referenz zum geprüften Dossier |
| doi\_valid | bool | Crossref-Check bestanden |
| nli\_entailment\_score | float (0–1) | NLI-Score: quell\_passage → kernaussage |
| numeric\_check\_passed | bool | Zahlenprüfung bestanden |
| profil\_similarity | float (0–1) | Embedding-Ähnlichkeit zum Gewerks-Profil |
| is\_duplicate\_of | str | None | ID des Duplikats (wenn erkannt) |
| quality\_approved | bool | Finale Freigabe für Publisher |
| feedback\_text | str | None | Textuelle Kritik für Re-Extraktion |
| iteration\_count | int | Anzahl der Evaluationsrunden (max 2\) |

## **3.6 Publisher Agent**

**Hierarchie:** Worker  |  **Phase:** 5  |  **LLM-Nutzung:** Ja (nur Formatierung, keine Faktenrecherche)

**Kernaufgabe:** Professionelles Layout und Formatierung der validierten Einzeldossiers. Der Publisher recherchiert keine neuen Fakten und verändert keine Inhalte – er transformiert nur das Ausgabeformat.

| Eigenschaft | Spezifikation |
| :---- | :---- |
| Input | list\[PublikationsDossierModel\] (quality\_approved=True) |
| Output (Pydantic) | PublikationsBerichtModel (finaler Bericht) |
| Formatierung | Markdown, DOCX oder strukturiertes JSON (konfigurierbar) |
| Metadaten | Automatische Anreicherung mit Timestamps, Gewerks-Referenz, Versionierung |
| Garantie | Keine inhaltlichen Änderungen – nur Layout und Lesbarkeit |
| Zusätzliche Outputs | Zusammenfassende Executive Summary über alle Dossiers |

# **4\. Vollständige Tool-Übersicht**

Alle Tools des Systems sind als typsichere Pydantic-AI-Tools implementiert, die über den RunContext injiziert werden:

| Tool | Agent | Extern/Intern | API / Mechanismus |
| :---- | :---- | :---- | :---- |
| search\_openalex\_keyword | Search Agent | Extern | OpenAlex REST /works (?search=) |
| search\_openalex\_semantic | Search Agent | Extern | OpenAlex REST /works (?search.semantic=) |
| search\_semantic\_scholar | Search Agent | Extern | Semantic Scholar /paper/search |
| search\_core | Search Agent | Extern | CORE API /search/works |
| get\_specter2\_embeddings | Search Agent | Extern | Semantic Scholar /paper/batch |
| find\_similar\_openalex | Search Agent | Extern | OpenAlex /works (Seed-based) |
| merge\_and\_rerank | Search Agent | Intern | RRF \+ Cosine Similarity |
| fetch\_fulltext\_core | Extraction Agent | Extern | CORE API /outputs/{id}/download |
| doi\_crossref\_check | Evaluator | Extern | Crossref REST /works/{doi} |
| source\_passage\_nli | Evaluator | Intern | DeBERTa-v3-large NLI-Modell |
| numeric\_cross\_check | Evaluator | Intern | Regex \+ LLM-Validation |
| profil\_relevanz\_check | Evaluator | Intern | SPECTER2 Cosine Similarity |
| format\_dossier\_md | Publisher | Intern | Jinja2 Templates |
| format\_dossier\_docx | Publisher | Intern | docx-js / python-docx |
| generate\_executive\_summary | Publisher | Intern | LLM-basierte Zusammenfassung |

# **5\. API-Integrationsstrategie**

## **5.1 Rate Limits und Kostenmanagement**

| API | Free Tier | Rate Limit | Kosten (Premium) | Empfehlung |
| :---- | :---- | :---- | :---- | :---- |
| OpenAlex | $1/Tag Budget | 10 req/s (polite pool) | Keyword: $0.0001 | Semantic: $0.001 | Polite-Pool mit mailto-Header |
| Semantic Scholar | Vollständig kostenlos | 5.000 req / 5 Min | n/a | API-Key für höhere Limits beantragen |
| CORE | Kostenlos (Basic) | 5 req / 10 Sek | Premium: unbegrenzt | Basic ausreichend für \<50 Gewerke/Tag |
| Crossref | Vollständig kostenlos | 50 req/s (polite) | n/a | Plus-API-Token für Priorität |

## **5.2 Kostenschätzung pro Gewerk**

Geschätzte Kosten für eine vollständige Recherche eines einzelnen Gewerks:

| Posten | Menge | Einzelpreis | Summe |
| :---- | :---- | :---- | :---- |
| OpenAlex Keyword-Queries | \~20 Queries | $0.0001 | $0.002 |
| OpenAlex Semantic-Queries | \~10 Queries | $0.001 | $0.01 |
| Semantic Scholar / CORE | \~30 Queries | $0.00 | $0.00 |
| LLM: Orchestrator (ToT) | \~5.000 Tokens | \~$0.01/1K | $0.05 |
| LLM: 30× Extraction Agents | \~60.000 Tokens | \~$0.003/1K | $0.18 |
| LLM: Evaluator (2 Iter.) | \~20.000 Tokens | \~$0.01/1K | $0.20 |
| LLM: Publisher | \~10.000 Tokens | \~$0.003/1K | $0.03 |
| **GESAMT pro Gewerk** |  |  | **\~$0.47** |

**Hochrechnung:** Für alle 145 Gewerke der HWO ergibt sich ein Gesamtaufwand von ca. $68 pro vollständigem Durchlauf. Bei monatlicher Aktualisierung sind das \~$816/Jahr – triviale Kosten im Vergleich zu manueller Recherche.

# **6\. Qualitätssicherung und Observability**

## **6.1 Mehrstufige Qualitätskontrolle**

Die Qualitätssicherung ist nicht auf den Evaluator beschränkt, sondern durchzieht alle Phasen:

| Phase | Mechanismus | Typ | Automatisch? |
| :---- | :---- | :---- | :---- |
| Phase 1 | Pydantic-Validierung des JSON-Profils | Schema-Enforcement | Ja |
| Phase 1 | ToT-Backtracking bei irrelevanten Forschungsfragen | Prompt-Engineering | Ja |
| Phase 2 | Null-Treffer-Erkennung \+ Query-Reformulierung | Adaptive Suche | Ja |
| Phase 2 | SPECTER2 Re-Ranking filtert schwach relevante Papers | Embedding-basiert | Ja |
| Phase 3 | Pydantic output\_type erzwingt strukturierte Dossiers | Schema-Enforcement | Ja |
| Phase 3 | Semaphore begrenzt parallele LLM-Aufrufe | Ressourcen-Management | Ja |
| Phase 4 | DOI-Verifikation via Crossref | Externe Validierung | Ja |
| Phase 4 | NLI-basierte Faktenprüfung gegen Quellpassage | Externe Validierung | Ja |
| Phase 4 | Numerische Cross-Checks | Regelbasiert | Ja |
| Phase 4 | Cross-Model-Evaluation (anderes LLM) | Bias-Reduktion | Ja |
| Phase 4 | Max 2 Iterationen mit Early-Stopping | Konvergenz-Kontrolle | Ja |
| Phase 5 | Keine inhaltlichen Änderungen durch Publisher | Architektonische Isolation | Ja |

## **6.2 Logfire-Observability**

Logfire wird nativ über logfire.instrument\_pydantic\_ai() eingebunden und protokolliert:

* **Agent-Delegationsbaum:** Vollständiger Trace von Orchestrator → Sub-Agenten mit Parent-Child-Beziehungen

* **Token-Verbrauch:** Aggregierter und pro-Agent-Token-Usage, zurechenbar zum Orchestrator

* **Latenz-Metriken:** Dauer jedes API-Calls, LLM-Aufrufs und Tool-Invocations

* **Evaluator-Loop-Tracing:** Exakte Nachvollziehbarkeit, welche Dossiers in welcher Iteration welches Feedback erhielten

* **Fehler-Alerting:** Automatische Benachrichtigung bei API-Timeouts, Validierungsfehlern oder Loop-Stalls

# **7\. Implementierungs-Roadmap**

Die Implementierung erfolgt in vier Sprints, wobei jeder Sprint ein lauffähiges Inkrement liefert:

## **Sprint 1: Foundation (Wochen 1–2)**

**Ziel:** Lauffähige Pipeline von JSON-Profil bis OpenAlex-Ergebnisliste

* Projekt-Setup: Python 3.12+, Pydantic v2, pydantic-ai, asyncio

* GewerksProfilModel definieren und mit 3 Beispiel-Gewerken validieren

* Profile Parsing Agent implementieren (rein deterministisch)

* Orchestrator mit vereinfachtem Prompting (ohne ToT) – generiert Keyword-Queries

* Search Agent mit OpenAlex Keyword-Search (?search=) implementieren

* Basis-Deduplizierung via DOI-Match

* **Deliverable:** CLI-Tool, das für ein Gewerk eine Liste relevanter OpenAlex-Papers ausgibt

## **Sprint 2: Retrieval-Optimierung (Wochen 3–4)**

**Ziel:** Föderierte Multi-Source-Suche mit SPECTER2-Re-Ranking

* Semantic Scholar und CORE API-Anbindungen hinzufügen

* SPECTER2-Embedding-Abruf und Cosine-Similarity-Re-Ranking implementieren

* Reciprocal Rank Fusion (RRF) für Multi-Source-Merging

* Bilinguale Query-Expansion (DE → EN) im Orchestrator

* Tree of Thoughts (ToT) Prompting für Forschungsfragen-Generierung

* HyDE-Abstracts für Semantic Search

* Erweiterte Deduplizierung (Jaro-Winkler \+ Embedding-Similarity)

* **Deliverable:** Hochqualitative, deduplizierte Publikationsliste aus drei Quellen

## **Sprint 3: Extraktion \+ Evaluation (Wochen 5–7)**

**Ziel:** Vollständige Pipeline von Profil bis validierte Dossiers

* Data Extraction Agent mit Fan-Out (asyncio.gather \+ Semaphore)

* PublikationsDossierModel mit quell\_passage für NLI-Verifikation

* CORE-Volltext-Integration für Papers mit verfügbarem Open-Access-Text

* Evaluator Agent mit Cross-Model-Setup (anderes LLM)

* DOI-Crossref-Check als Hard Gate

* NLI-basierte Source-Passage-Verifikation (DeBERTa-v3)

* Evaluator-Optimizer-Loop mit max 2 Iterationen \+ Early-Stopping

* Logfire-Integration für Full-Stack-Tracing

* **Deliverable:** Validierte Einzeldossiers mit nachvollziehbarer Qualitätsbewertung

## **Sprint 4: Publisher \+ Produktion (Wochen 8–10)**

**Ziel:** Produktionsreifes System mit professionellem Output

* Publisher Agent mit konfigurierbaren Output-Formaten (MD, DOCX, JSON)

* Executive-Summary-Generierung über alle Dossiers eines Gewerks

* Concept-Discovery-Feedback-Loop (Evaluator → Search Agent)

* Batch-Processing für alle 145 HWO-Gewerke

* Error-Recovery und Retry-Strategien für API-Ausfälle

* Performance-Optimierung (Caching, Connection-Pooling)

* Dokumentation und Deployment-Konfiguration

* **Deliverable:** Produktionsreifes CLI/API-System für vollautomatisierte Gewerke-Recherche

# **8\. Risiken und Mitigationsstrategien**

| Risiko | Schwere | Wahrsch. | Mitigation |
| :---- | :---- | :---- | :---- |
| OpenAlex-Ausfall / Rate-Limit | Hoch | Niedrig | Fallback auf Semantic Scholar; exponentielles Backoff; lokaler Cache |
| LLM-Halluzinationen in Dossiers | Hoch | Mittel | Tool-basierte Verifikation (NLI, DOI-Check); Cross-Model-Evaluation |
| Evaluator-Loop konvergiert nicht | Mittel | Niedrig | Hard Cap bei 2 Iterationen; Early-Stopping bei ähnlichem Feedback |
| SPECTER2-Embeddings nicht verfügbar | Mittel | Niedrig | Fallback auf OpenAlex GTE-Large; lokaler SPECTER2-Inference |
| Graue Literatur nicht abgedeckt | Mittel | Hoch | Transparente Kennzeichnung in Dossiers; zukünftige BAuA/DGUV-Integration |
| Deutsche Fachterminologie wird nicht gefunden | Hoch | Mittel | Bilinguale Queries; HyDE-Abstracts; Fraunhofer-Institutionsfilter |
| Token-Kosten eskalieren | Niedrig | Niedrig | UsageLimits pro Agent; Semaphore für Parallelität; Monitoring via Logfire |
| Pydantic-Validierung blockiert gültige Dossiers | Mittel | Niedrig | Schrittweise Schema-Verschärfung; Logging aller Validierungsfehler |

