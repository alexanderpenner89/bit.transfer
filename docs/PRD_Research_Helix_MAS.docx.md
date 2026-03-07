

**PRODUCT REQUIREMENTS DOCUMENT**

Research Helix

LLM-basiertes Multi-Agenten-System für

gewerkespezifische Publikationsrecherche

Version 1.0  •  März 2026  •  6 Epics  •  28 User Stories

# **Inhaltsverzeichnis**

# **1\. Produktvision und Problemstellung**

## **1.1 Problem Statement**

Handwerksbetriebe und Handwerkskammern haben keinen systematischen Zugang zu wissenschaftlichen Publikationen, die für ihre spezifischen Gewerke relevant sind. Die Informationslücke zwischen akademischer Forschung und handwerklicher Praxis führt dazu, dass technologische Innovationen, neue Materialien, ergonomische Erkenntnisse und Verfahrensoptimierungen die Betriebe nicht oder erst mit großer Verzögerung erreichen.

Eine manuelle Literaturrecherche für ein einzelnes Gewerk dauert 2–4 Wochen und erfordert sowohl wissenschaftliche als auch handwerkliche Fachkenntnis – eine Kombination, die selten in einer Person vereint ist. Für alle 145 Gewerke der Handwerksordnung (HWO) ist eine manuelle Recherche ökonomisch nicht durchführbar.

## **1.2 Produktvision**

| Vision Statement Research Helix automatisiert die gewerkespezifische wissenschaftliche Literaturrecherche vollständig. Das System nimmt ein strukturiertes Gewerks-Profil entgegen und liefert innerhalb von Minuten einen validierten, publikationsbereiten Forschungsbericht mit Einzeldossiers zu relevanten wissenschaftlichen Arbeiten – für jedes der 145 Gewerke der deutschen Handwerksordnung. |
| :---- |

## **1.3 Zielgruppen und Personas**

| Persona | Rolle | Kernbedürfnis | Nutzungshäufigkeit |
| :---- | :---- | :---- | :---- |
| Berater:in HWK | Technologie-Berater bei einer Handwerkskammer | Schneller Überblick über relevante Forschung für Beratungsgespräche | Wöchentlich |
| Betriebsinhaber:in | Führt einen Handwerksbetrieb | Neue Materialien, Verfahren, Normen für den eigenen Betrieb | Monatlich |
| Verbandsreferent:in | Arbeitet bei einem Fachverband | Systematische Branchenanalyse für Positionspapiere | Quartalsweise |
| Forscher:in | Angewandte Forschung (z.B. Fraunhofer) | Identifikation von Transferpotenzial in Handwerksgewerke | Projektbezogen |

## **1.4 Scope und Abgrenzung**

| Kategorie | In Scope (v1.0) | Out of Scope (spätere Version) |
| :---- | :---- | :---- |
| Datenquellen | OpenAlex, Semantic Scholar, CORE | BAuA, DGUV, Fraunhofer-Reports, DIN-Normen |
| Gewerke | Alle 145 HWO-Gewerke (Anlage A, B1, B2) | Freie Gewerke ohne HWO-Eintrag |
| Sprachen | Deutsch \+ Englisch (bilingual) | Französisch, weitere Sprachen |
| Output | DOCX, Markdown, JSON pro Gewerk | Web-Dashboard, E-Mail-Alerts |
| Betrieb | CLI-Tool, Batch-Modus | REST-API, Multi-Tenant SaaS |
| Update-Modus | Vollständige Recherche pro Lauf | Inkrementelle Delta-Updates |
| Qualitätssicherung | Automatisch (NLI, DOI-Check, Cross-Model) | Human-in-the-Loop Review-Workflow |

# **2\. Epic-Übersicht**

Das Produkt wird in 6 Epics gegliedert, die den Datenfluss durch die Pipeline abbilden. Jedes Epic enthält User Stories mit Akzeptanzkriterien, Priorität und Story Points.

| Epic | Titel | Stories | SP | Meilenstein | Kernfrage |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **E1** | Gewerks-Profil-Management | 5 | 18 | M1 | Sind die Profile korrekt und vollständig? |
| **E2** | Intelligente Themenidentifikation | 4 | 16 | M1–M2 | Generiert das LLM relevante Forschungsfragen? |
| **E3** | Föderiertes Publikations-Retrieval | 6 | 26 | M1–M3 | Finden wir die relevante Literatur? |
| **E4** | Parallele Dossier-Extraktion | 4 | 18 | M2 | Extrahiert das LLM korrekte Informationen? |
| **E5** | Automatische Qualitätssicherung | 5 | 24 | M3 | Erkennen wir Fehler zuverlässig? |
| **E6** | Publikation und Betrieb | 4 | 16 | M4 | Ist der Output nutzbar und der Betrieb stabil? |
| **GESAMT** |  | **28** | **118** |  |  |

## **2.1 Epic-Abhängigkeiten**

Die Epics haben eine klare Abhängigkeitsstruktur entlang der Pipeline:

**E1** (Profile) → **E2** (Themen) → **E3** (Retrieval) → **E4** (Extraktion) → **E5** (Qualität) → **E6** (Publikation)

E1 und E2 können teilweise parallel entwickelt werden. E3 ist das umfangreichste Epic und wird über drei Meilensteine inkrementell ausgebaut. E5 hat eine Rückwirkung auf E4 (Feedback-Loop) und E3 (Concept Discovery).

# **3\. Epics und User Stories**

| E1  Gewerks-Profil-Management |
| :---: |

**Epic Owner:** Backend  |  **Meilenstein:** M1  |  **Story Points:** 18

**Ziel:** Alle 145 HWO-Gewerke sind als validierte, maschinenlesbare JSON-Profile verfügbar, die als deterministischer Startpunkt für die gesamte Pipeline dienen.

| E1-S1  Gewerks-Profil-Schema definieren    Priorität: P0 – Must  |  M1  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **Entwickler** möchte ich **ein vollständiges Pydantic-Schema für Gewerks-Profile definieren**, damit alle nachfolgenden Agenten ein typsicheres, validiertes Datenobjekt erhalten. |
| **Akzeptanz-kriterien** | GewerksProfilModel deckt alle Felder ab: gewerk\_id, gewerk\_name, hwo\_anlage, kernkompetenzen, taetigkeitsfelder, techniken (manuell/maschinell/oberflaeche), werkstoffe, software\_tools, arbeitsbedingungen Feld hwo\_anlage ist auf Literal\['A','B1','B2'\] beschränkt Alle list\[str\]-Felder haben min\_length=1 Constraint Modell hat JSON-Schema-Export für Dokumentation |

| E1-S2  Profile Parsing Agent implementieren    Priorität: P0 – Must  |  M1  |  2 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **JSON-Dateien einlesen und gegen das Schema validieren**, damit fehlerhafte Profile sofort mit präzisen Fehlermeldungen abgelehnt werden. |
| **Akzeptanz-kriterien** | Agent liest JSON-Datei von Dateisystem oder als String-Input ValidationError gibt exaktes Feld und erwarteten Typ an Agent nutzt kein LLM – rein deterministisch Verarbeitung \< 100ms pro Profil |

| E1-S3  3 Pilotgewerke als JSON-Profile erstellen    Priorität: P0 – Must  |  M1  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **Fachberater** möchte ich **validierte Profile für Tischler (A), Fliesenleger (B1) und Kosmetiker (B2) haben**, damit ich die Pipeline mit realistischen Testdaten evaluieren kann. |
| **Akzeptanz-kriterien** | Jedes Profil enthält ≥10 Kernkompetenzen und ≥15 Techniken Jedes Profil besteht GewerksProfilModel-Validierung Profile wurden von einem Fachexperten auf inhaltliche Korrektheit geprüft Profile sind repräsentativ für die drei HWO-Anlage-Typen |

| E1-S4  LLM-gestützte Profil-Generierung für alle 145 Gewerke    Priorität: P1 – Should  |  M4  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **Projektleiter** möchte ich **Profile für alle 145 Gewerke automatisch generieren und manuell validieren lassen**, damit der Batch-Modus über die gesamte HWO laufen kann. |
| **Akzeptanz-kriterien** | LLM generiert Profile basierend auf HWO-Beschreibungen und Berufenet-Daten Alle generierten Profile bestehen GewerksProfilModel-Validierung Erste 20 Profile werden manuell von Fachexperten geprüft und korrigiert Korrigierte Profile dienen als Few-Shot-Beispiele für die restlichen 125 |

| E1-S5  Profil-Versionierung und Changelog    Priorität: P2 – Could  |  M4  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **Fachberater** möchte ich **nachvollziehen können, wann ein Profil zuletzt geändert wurde**, damit ich weiß, ob die Rechercheergebnisse auf aktuellen Profildaten basieren. |
| **Akzeptanz-kriterien** | Jedes Profil hat ein version-Feld (semver) und last\_updated (ISO 8601\) Bei Änderungen wird die Version automatisch inkrementiert Änderungshistorie wird in separater Changelog-Datei gespeichert |

| E2  Intelligente Themenidentifikation |
| :---: |

**Epic Owner:** AI/ML  |  **Meilenstein:** M1–M2  |  **Story Points:** 16

**Ziel:** Aus dem Gewerks-Profil werden automatisch hochspezifische, bilinguale Forschungsfragen und Suchstrategien generiert, die relevante Literatur maximal präzise identifizieren.

| E2-S1  Regelbasierte Keyword-Extraktion (MVP)    Priorität: P0 – Must  |  M1  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **Suchbegriffe direkt aus den Profilfeldern extrahieren**, damit die Pipeline ohne LLM-Abhängigkeit für die Themenidentifikation lauffähig ist. |
| **Akzeptanz-kriterien** | Extrahiert Keywords aus kernkompetenzen, techniken\_manuell, techniken\_maschinell, werkstoffe Generiert Boole’sche Queries mit AND/OR-Kombination Mindestens 5 verschiedene Queries pro Gewerk Keine LLM-Nutzung – rein regelbasiert |

| E2-S2  LLM-basierte Forschungsfragen-Generierung    Priorität: P0 – Must  |  M2  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **mittels Chain-of-Thought aus dem Gewerks-Profil spezifische Forschungsfragen ableiten**, damit die Suche über einfache Keywords hinausgeht und kontextuelle Zusammenhänge erkennt. |
| **Akzeptanz-kriterien** | Orchestrator-Agent generiert 3–10 Forschungsfragen pro Gewerk Jede Forschungsfrage hat einen erklärten Bezug zu mindestens einem Profilfeld Output ist ein validiertes SearchStrategyModel Prompting-Strategie: Chain-of-Thought mit Profil-Kontext im System-Prompt |

| E2-S3  Bilinguale Query-Expansion (DE → EN)    Priorität: P0 – Must  |  M2  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **zu jeder deutschen Suchanfrage automatisch englische Varianten generieren**, damit auch internationale Forschung gefunden wird, die deutsche Fachbegriffe nicht enthält. |
| **Akzeptanz-kriterien** | Jede deutsche Keyword-Query hat mindestens 2 englische Varianten Zusätzlich: 2–3 englische Absatz-Descriptions für Semantic Search Optional: HyDE-Abstracts (hypothetische Abstracts für Embedding-Suche) Bilinguale Queries erhöhen Recall um ≥20% vs. nur-deutsche Queries |

| E2-S4  Tree of Thoughts mit automatischem Backtracking    Priorität: P2 – Could  |  M4  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **mehrere Argumentationslinien parallel explorieren und irrelevante verwerfen**, damit die Forschungsfragen eng am Profil bleiben und keine thematischen Sackgassen verfolgen. |
| **Akzeptanz-kriterien** | ToT generiert 3 parallele Gedankenbäume pro Gewerk Jeder Zweig wird gegen das Gewerks-Profil auf Relevanz bewertet Irrelevante Äste (Score \< 0.3) werden automatisch geprunt Resultierende Forschungsfragen decken ≥80% der Profilfelder ab |

| E3  Föderiertes Publikations-Retrieval |
| :---: |

**Epic Owner:** Backend  |  **Meilenstein:** M1–M3  |  **Story Points:** 26

**Ziel:** Relevante Publikationen werden aus drei föderierten Quellen (OpenAlex, Semantic Scholar, CORE) abgerufen, dedupliziert und mit wissenschaftsspezifischen Embeddings re-gerankt.

| E3-S1  OpenAlex Keyword-Suche    Priorität: P0 – Must  |  M1  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **Publikationen über den OpenAlex ?search= Endpunkt finden**, damit die Basis-Retrieval-Pipeline für den MVP funktioniert. |
| **Akzeptanz-kriterien** | Tool search\_openalex\_keyword ist als Pydantic-AI-Tool implementiert Nutzt polite-pool mit mailto-Header (10 req/s) Unterstützt Boole’sche Operatoren (AND, OR, NOT) und .no\_stem Cursor-basierte Pagination für \>200 Ergebnisse Response wird in OpenAlexWorkModel geparst |

| E3-S2  OpenAlex Semantic Search    Priorität: P1 – Should  |  M2  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **konzeptionell verwandte Publikationen via Embedding-Suche finden**, damit auch Papers gefunden werden, deren Terminologie von der Handwerkspraxis abweicht. |
| **Akzeptanz-kriterien** | Tool search\_openalex\_semantic nutzt ?search.semantic= Endpunkt Akzeptiert Absatz-lange Beschreibungen als Query (nicht nur Keywords) Kostenaware: Semantic Search kostet 10× mehr als Keyword ($0.001 vs. $0.0001) Ergebnisse werden mit Keyword-Ergebnissen gemergt (Union über DOI) |

| E3-S3  Semantic Scholar Integration    Priorität: P1 – Should  |  M3  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **SPECTER2-Embeddings und Zitationsdaten von Semantic Scholar abrufen**, damit das Re-Ranking auf wissenschaftsspezifischen Embeddings basiert statt auf General-Purpose-Modellen. |
| **Akzeptanz-kriterien** | Tool search\_semantic\_scholar durchsucht S2 /paper/search Tool get\_specter2\_embeddings ruft Batch-Embeddings ab (max 500/Request) S2-Paper werden über DOI mit OpenAlex-Ergebnissen gematcht Rate Limit: 5.000 req / 5 Min (kostenlos) |

| E3-S4  CORE Volltext-Integration    Priorität: P1 – Should  |  M3  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **Open-Access-Volltexte über CORE abrufen**, damit die Extraktion auf vollständigen Texten statt nur Abstracts basieren kann. |
| **Akzeptanz-kriterien** | Tool search\_core durchsucht CORE /search/works Tool fetch\_fulltext\_core lädt Volltexte herunter Volltext wird als zusätzlicher Kontext an den Extraction Agent übergeben Fallback: Wenn kein Volltext verfügbar, wird nur Abstract genutzt (mit Kennzeichnung) |

| E3-S5  Multi-Source Deduplizierung    Priorität: P0 – Must  |  M1 (S1) → M3 (S2–S4)  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **Duplikate aus drei Quellen zuverlässig erkennen und zusammenführen**, damit keine Publikation doppelt extrahiert wird und Preprints mit Published-Versionen zusammengeführt werden. |
| **Akzeptanz-kriterien** | Stufe 1: Exakter DOI-Match Stufe 2: Normalisierter Titel \+ Erstautor \+ Jahr mit Jaro-Winkler \>0.95 Stufe 3: SPECTER2 Embedding-Similarity \>0.95 für Grenzfälle Stufe 4: Preprint-zu-Published-Mapping (bevorzuge Peer-Reviewed) Sensitivity ≥0.95, Specificity ≥0.99 |

| E3-S6  SPECTER2 Re-Ranking mit Reciprocal Rank Fusion    Priorität: P1 – Should  |  M3  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **Ergebnisse aus allen Quellen nach wissenschaftlicher Relevanz neu sortieren**, damit die Top-k Papers tatsächlich die relevantesten für das spezifische Gewerk sind. |
| **Akzeptanz-kriterien** | Tool merge\_and\_rerank berechnet Cosine-Similarity zwischen Paper-Embeddings und Gewerks-Profil-Embedding Reciprocal Rank Fusion (RRF) kombiniert Rankings aus Keyword, Semantic und S2-Suche Re-Ranking verbessert Precision@20 um ≥10 Prozentpunkte vs. ohne Re-Ranking Top-k ist konfigurierbar (Default: 30\) |

| E4  Parallele Dossier-Extraktion |
| :---: |

**Epic Owner:** AI/ML  |  **Meilenstein:** M2  |  **Story Points:** 18

**Ziel:** Für jede als relevant identifizierte Publikation wird ein strukturiertes Einzeldossier extrahiert – massiv parallelisiert, isoliert und schema-enforced.

| E4-S1  Data Extraction Agent mit Fan-Out    Priorität: P0 – Must  |  M2  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **für jedes Paper parallel eine isolierte Extraction-Instanz starten**, damit die Extraktion skaliert und das Lost-in-the-Middle-Problem vermieden wird. |
| **Akzeptanz-kriterien** | asyncio.gather() startet n Agenten parallel (eine pro Paper) Semaphore begrenzt Concurrency auf max 10 gleichzeitige LLM-Calls Jede Instanz erhält genau 1 Paper \+ GewerksProfilModel via RunContext Output: PublikationsDossierModel (validiert durch Pydantic output\_type) 30 Dossiers werden in \< 3 Minuten generiert |

| E4-S2  PublikationsDossierModel definieren    Priorität: P0 – Must  |  M2  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **ein vollständiges, typsicheres Schema für Einzeldossiers erzwingen**, damit alle Dossiers ein einheitliches Format haben und maschinell weiterverarbeitbar sind. |
| **Akzeptanz-kriterien** | Felder: paper\_id, titel, autoren, jahr, quelle, kernaussage, methodik, methodik\_validiert (bool), relevanz\_fuer\_gewerk, relevanz\_score (0–1), schluesselzahlen, limitationen, volltext\_verfuegbar (bool), quell\_passage quell\_passage enthält die exakte Textpassage, auf der kernaussage basiert relevanz\_score wird vom LLM auf einer 0–1-Skala vergeben Pydantic-Validierung lehnt unvollständige Dossiers ab (kein optionales Feld) |

| E4-S3  Volltext-Extraktion (CORE-erweitert)    Priorität: P1 – Should  |  M3  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **bei verfügbarem Volltext eine tiefere Extraktion durchführen**, damit die Dossier-Qualität für Papers mit Open-Access-Volltext deutlich höher ist. |
| **Akzeptanz-kriterien** | Wenn CORE Volltext liefert: Extraction Agent erhält Volltext statt nur Abstract Volltext wird auf relevanteste Sektionen vorextrahiert (Methods, Results, Discussion) Feld volltext\_verfuegbar zeigt an, ob Volltext oder Abstract genutzt wurde Volltext-basierte Dossiers haben nachweislich höhere Experten-Bewertung |

| E4-S4  Token-Budget und UsageLimits pro Agent    Priorität: P1 – Should  |  M2  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **den Token-Verbrauch pro Extraktion begrenzen**, damit die Kosten pro Gewerk vorhersagbar und kontrollierbar bleiben. |
| **Akzeptanz-kriterien** | Pydantic-AI UsageLimits: max 2.000 Output-Tokens pro Dossier Gesamtbudget pro Gewerk: max 100.000 Tokens (alle Agents zusammen) Logfire trackt Token-Verbrauch pro Agent und pro Gewerk Überschreitung erzeugt Warning, kein Hard-Abort |

| E5  Automatische Qualitätssicherung |
| :---: |

**Epic Owner:** AI/ML \+ Backend  |  **Meilenstein:** M3  |  **Story Points:** 24

**Ziel:** Automatische Verifikation aller Dossiers durch tool-basierte externe Prüfung (nicht LLM-Selbstkorrektur). Cross-Model-Evaluation und Evaluator-Optimizer-Loop mit max 2 Iterationen.

| Design-Prinzip Der Evaluator verlässt sich NICHT auf LLM-Urteil allein. Jede Qualitätsprüfung ist an ein externes, deterministisches Tool gebunden. Das LLM koordiniert die Tools und interpretiert deren Ergebnisse – es fällt keine unverankerten Urteile. |
| :---- |

| E5-S1  DOI-Verifikation via Crossref    Priorität: P0 – Must  |  M3  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **Evaluator Agent** möchte ich **die Existenz jeder zitierten Publikation extern verifizieren**, damit erfundene oder halluzinierte Referenzen erkannt und aussortiert werden. |
| **Akzeptanz-kriterien** | Tool doi\_crossref\_check ruft Crossref /works/{doi} auf Prüft: DOI existiert, Titelähnlichkeit \>0.8 (Jaro-Winkler), Jahr stimmt Hard Gate: FAIL bei nicht-existenter DOI oder Metadaten-Mismatch Kostenfrei, Rate Limit: 50 req/s mit polite-pool 100% der nicht-existenten DOIs werden erkannt |

| E5-S2  NLI-basierte Faktenprüfung    Priorität: P0 – Must  |  M3  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **Evaluator Agent** möchte ich **prüfen ob die extrahierte Kernaussage durch die Quellpassage gestützt wird**, damit inhaltliche Halluzinationen erkannt werden, bevor sie im Output landen. |
| **Akzeptanz-kriterien** | Tool source\_passage\_nli nutzt lokales DeBERTa-v3-large NLI-Modell Input: (quell\_passage, kernaussage) → Output: entailment/neutral/contradiction \+ Score Hard Gate: contradiction ODER entailment-score \< 0.5 → FAIL False-Positive-Rate \< 10% auf manuell annotierten Testdaten Modell läuft lokal (kein API-Call, keine Kosten) |

| E5-S3  Numerische Cross-Checks    Priorität: P1 – Should  |  M3  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **Evaluator Agent** möchte ich **extrahierte Zahlen automatisch gegen die Quellpassage abgleichen**, damit quantitative Aussagen in den Dossiers korrekt sind. |
| **Akzeptanz-kriterien** | Tool numeric\_cross\_check extrahiert alle Zahlen aus quell\_passage und schluesselzahlen per Regex Abgleich: Jede Zahl in schluesselzahlen muss in quell\_passage vorkommen Soft Gate: Fehlende Zahlen erzeugen Warnung, keinen Ausschluss Toleranz: ±1% für Rundungsdifferenzen |

| E5-S4  Evaluator-Optimizer-Loop mit Feedback    Priorität: P0 – Must  |  M3  |  8 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **fehlerhafte Dossiers mit textueller Kritik zurückdelegieren und verbessern lassen**, damit die Gesamtqualität durch gezielte Nachbesserung steigt ohne menschliches Eingreifen. |
| **Akzeptanz-kriterien** | Dossiers mit Soft-Gate-Failures erhalten strukturiertes Feedback (EvaluationResultModel.feedback\_text) Feedback wird an den Extraction Agent zurückdelegiert (gleiche Instanz, neuer Versuch) Maximal 2 Iterationen (Hard Cap, nicht konfigurierbar) Early-Stopping: Wenn Feedback-Text Cosine-Similarity \>0.9 zur vorherigen Iteration hat, Abbruch Konvergenzrate: ≥95% der Dossiers terminieren in ≤2 Iterationen |

| E5-S5  Cross-Model-Evaluation    Priorität: P1 – Should  |  M3  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **für die Evaluation ein anderes LLM nutzen als für die Extraktion**, damit Self-Enhancement-Bias vermieden wird und Fehler aus Modell-blinden Flecken erkannt werden. |
| **Akzeptanz-kriterien** | Wenn Extraction Agent \= Claude Sonnet → Evaluator \= GPT-4o (oder umgekehrt) Evaluator-Modell ist per Konfiguration wechselbar A/B-Test zeigt: Cross-Model findet ≥15% mehr Fehler als Same-Model Token-Kosten für Evaluator sind separat trackbar in Logfire |

| E6  Publikation und Betrieb |
| :---: |

**Epic Owner:** Backend \+ DevOps  |  **Meilenstein:** M4  |  **Story Points:** 16

**Ziel:** Die validierten Dossiers werden in professionellen Formaten publiziert. Das System läuft stabil im Batch-Modus über alle 145 Gewerke mit vollständiger Observability.

| E6-S1  Publisher Agent mit Multi-Format-Export    Priorität: P0 – Must  |  M4  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **Fachberater** möchte ich **Rechercheergebnisse als professionell formatiertes Word-Dokument erhalten**, damit ich die Ergebnisse direkt in Beratungsgesprächen und Präsentationen einsetzen kann. |
| **Akzeptanz-kriterien** | DOCX-Export: Deckblatt, Inhaltsverzeichnis, formatierte Dossiers, Executive Summary Markdown-Export: Für Webseiten und Knowledge-Base-Systeme JSON-Export: Für maschinelle Weiterverarbeitung und API-Anbindung Publisher ändert keine Inhalte – nur Layout und Formatierung Konfigurierbar via CLI-Flag: \--format docx|md|json|all |

| E6-S2  Batch-Verarbeitung für 145 Gewerke    Priorität: P0 – Must  |  M4  |  5 SP |  |
| :---- | :---- |
| **User Story** | Als **Projektleiter** möchte ich **alle 145 Gewerke in einem Durchlauf verarbeiten**, damit ein vollständiger Forschungsüberblick für die gesamte HWO entsteht. |
| **Akzeptanz-kriterien** | CLI: python \-m research\_helix batch \--all \--output-dir ./results/ Sequenzielle Gewerk-Verarbeitung mit Fortschrittsbalken (tqdm) Checkpoint-System: Bei Crash wird ab letztem erfolgreichem Gewerk fortgesetzt Gesamtdauer \< 24 Stunden für alle 145 Gewerke Fehlerrate \< 5% (max 7 Gewerke mit Problemen) |

| E6-S3  Error Recovery und Caching    Priorität: P1 – Should  |  M4  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **System** möchte ich **API-Ausfälle automatisch kompensieren und unnötige Requests vermeiden**, damit der Batch-Lauf robust gegen temporäre Netzwerkprobleme ist und Kosten minimiert werden. |
| **Akzeptanz-kriterien** | Exponentielles Backoff (1s, 2s, 4s, 8s) für alle externen APIs Fallback-Kette: OpenAlex → Semantic Scholar → Skip mit Warnung Lokaler Response-Cache (SQLite): 24h TTL für Suchen, 7 Tage für Metadaten Cache-Hit-Rate \> 60% bei erneutem Lauf innerhalb von 24h Max 3 Retries pro Gewerk, dann Skip \+ Logging |

| E6-S4  Logfire-Dashboard und Alerting    Priorität: P1 – Should  |  M4  |  3 SP |  |
| :---- | :---- |
| **User Story** | Als **Entwickler** möchte ich **den Systemzustand in Echtzeit überwachen und bei Problemen benachrichtigt werden**, damit Fehler schnell erkannt und behoben werden können. |
| **Akzeptanz-kriterien** | Dashboard zeigt: Erfolgsrate, Dossier-Qualität, Token-Kosten, API-Latenz pro Gewerk Alert: E-Mail bei Fehlerrate \> 10% oder API-Ausfall \> 5 Minuten Alle Agent-Delegationen sind als Traces mit Parent-Child-Beziehungen sichtbar Token-Usage ist pro Agent und pro Gewerk aufschlüsselbar |

# **4\. Nicht-funktionale Anforderungen**

| Kategorie | Anforderung | Metrik | Zielwert |
| :---- | :---- | :---- | :---- |
| Performance | Recherche-Dauer pro Gewerk | Wall-Clock-Time | \< 10 Minuten |
| Performance | Batch-Lauf (145 Gewerke) | Wall-Clock-Time | \< 24 Stunden |
| Kosten | API \+ LLM-Kosten pro Gewerk | USD | \< $0.70 |
| Kosten | Batch-Lauf gesamt | USD | \< $100 |
| Qualität | Dossier-Korrektheit (Experte) | % brauchbar | ≥ 85% |
| Qualität | Halluzinationsrate | % NLI contradiction | \< 5% |
| Qualität | DOI-Validität | % gültige DOIs | 100% |
| Zuverlässigkeit | Batch-Fehlerrate | % fehlerhafte Gewerke | \< 5% |
| Zuverlässigkeit | API-Timeout-Recovery | % erfolgreiche Retries | \> 90% |
| Skalierbarkeit | Gleichzeitige Extraktionen | Concurrent Agents | ≥ 10 |
| Observability | Trace-Abdeckung | % getrackte Agent-Calls | 100% |
| Sicherheit | API-Keys in Env-Vars | Keine Hardcoded Secrets | Ja |
| Wartbarkeit | Test-Abdeckung | Line Coverage | ≥ 70% |

# **5\. Priorisierung und Release-Planung**

## **5.1 MoSCoW-Übersicht**

| Priorität | Stories | SP | Beschreibung |
| :---- | :---- | :---- | :---- |
| **P0 – Must Have** | 14 | 64 | Kernfunktionalität ohne die das Produkt keinen Wert hat. Alle Meilenstein-Gates hängen davon ab. |
| **P1 – Should Have** | 10 | 40 | Signifikante Qualitätsverbesserungen. Werden in M2–M4 implementiert wenn Zeitplan hält. |
| **P2 – Could Have** | 4 | 14 | Nice-to-haves die den Wert erhöhen. Werden priorisiert wenn Sprints schneller laufen als geplant. |
| **GESAMT** | **28** | **118** |  |

## **5.2 Release-Plan**

| Release | Meilenstein | Stories | Woche | Nutzer-Wert |
| :---- | :---- | :---- | :---- | :---- |
| v0.1-alpha | M1 | E1-S1, E1-S2, E1-S3, E2-S1, E3-S1, E3-S5 (Stufe 1\) | 2 | Erster Beweis: relevante Papers für Gewerke existieren |
| v0.2-alpha | M2 | \+ E2-S2, E2-S3, E3-S2, E4-S1, E4-S2, E4-S4 | 5 | Erste nutzbare Dossiers – Fachexperten können evaluieren |
| v0.9-beta | M3 | \+ E3-S3, E3-S4, E3-S5 (voll), E3-S6, E5-S1–S5 | 8 | Automatisch verifizierte Qualität – System ist vertrauenswürdig |
| v1.0 | M4 | \+ E1-S4, E4-S3, E6-S1–S4, E1-S5, E2-S4 | 10 | Produktionsreif: 145 Gewerke, professionelle Reports |

# **6\. Glossar**

| Begriff | Definition |
| :---- | :---- |
| HWO | Handwerksordnung – Bundesgesetz, das die 145 Gewerke in Anlage A (zulassungspflichtig), B1 (zulassungsfrei) und B2 (handwerksähnlich) einteilt |
| Gewerk | Ein spezifisches Handwerk gemäß HWO (z.B. Tischler, Maurer, Elektrotechniker) |
| Dossier | Strukturierter Einzelbericht zu einer wissenschaftlichen Publikation mit Kernaussage, Methodik, Relevanz und Quellverifikation |
| Fan-Out | Architekturmuster: Parallel-Ausführung identischer Agent-Instanzen für verschiedene Datensätze |
| NLI | Natural Language Inference – KI-Aufgabe zur Bestimmung ob eine Hypothese aus einer Prämisse folgt |
| SPECTER2 | Wissenschaftsspezifisches Embedding-Modell von Allen AI, trainiert auf 6M Zitationstripeln |
| RRF | Reciprocal Rank Fusion – Methode zum Kombinieren mehrerer Rankings ohne Score-Normalisierung |
| HyDE | Hypothetical Document Embeddings – Technik zur Verbesserung von Zero-Shot-Retrieval |
| ToT | Tree of Thoughts – Prompting-Framework für parallele Exploration von Argumentationslinien |
| Polite Pool | OpenAlex-Konzept: Höheres Rate Limit (10 req/s) bei Angabe einer mailto-Adresse |

