# ACCOUNTING BLUEPRINT - EduConnect Engine

## 0. Jalon stable post-Phase 6.2 (2026-08-02)

Ce blueprint reste la cible d'architecture V1. Le statut actuel atteint et valide est:

- Shared Kernel
- JournalEntry / JournalLine
- RecordJournalEntry
- PostJournalEntry
- ReverseJournalEntry
- Ledger Projection
- Trial Balance Projection
- Balance Sheet Projection
- Income Statement Projection
- Financial Statements Projection
- Accounting Period Lifecycle
- Fiscal Year Closing

Prochaine phase exacte:

- Phase 6.3 - Closing Entries & Opening Entries

Etat qualite de reference:

- Ruff: pass
- MyPy: pass
- Pytest: 379 tests passes
- Couverture globale: 97%

Dettes techniques connues (sans impact metier immediat):

- compatibilite legacy maintenue autour de `Account` dans le package accounting racine
- placeholder legacy conserve dans `accounting/domain/entities.py` (note de deprecation)
- surface d'exports publics large dans `accounting/domain/__init__.py` (a rationaliser lors de la stabilisation API publique)

Hors perimetre actuel:

- adapters SQL/ORM
- API HTTP
- orchestration asynchrone/event bus
- consolidation multi-entites
- fiscalite avancee

## 1. Perimetre du moteur comptable

Le moteur comptable couvre la tenue comptable en partie double, la production des etats financiers de base, la tracabilite des operations et la preparation des donnees fiscales suisses necessaires aux obligations periodiques.

Le perimetre fonctionnel V1 inclut:
- gestion du plan comptable
- enregistrement, validation et comptabilisation des ecritures
- generation du grand livre
- generation de la trial balance
- generation du bilan
- generation du compte de resultat
- cloture de periode
- piste d'audit

Le perimetre V1 exclut toute automatisation IA de decision comptable.

## 2. Bounded Contexts

Le moteur comptable est decoupe en contextes metier:

- Chart Of Accounts Context
  - responsabilite: structure et gouvernance des comptes
- Journal Context
  - responsabilite: creation, validation et comptabilisation des ecritures
- Ledger Projection Context
  - responsabilite: projections deterministes reconstruites depuis le Journal
- Financial Statements Context
  - responsabilite: vues bilan/compte de resultat/trial balance derivees de la trial balance
- Period Closing Context
  - responsabilite: verrouillage de periode, controles de cloture, report a nouveau

Regles de frontiere:
- un contexte ne lit pas les tables internes d'un autre contexte
- la collaboration se fait via cas d'utilisation applicatifs et contrats explicites
- aucune coherence eventual consistency en V1

## 3. Matrice de responsabilites inter-contextes

| Contexte | Ownership principal | Entrees | Sorties | Hors responsabilite |
|---|---|---|---|---|
| accounting | journal, plan de comptes, cloture, projections ledger/trial balance | operations metier comptables | trial balance, etats financiers de base, evenements internes | parametrage fiscal avance, analyse financiere avancee |
| tax | regles fiscales suisses, calculs fiscaux et obligations fiscales | assiettes comptables preparees par accounting | declarations/justificatifs fiscaux | ecriture comptable source |
| finance | pilotage financier, budget, analyses de gestion | sorties comptables consolidees | indicateurs de pilotage | moteur d'ecriture comptable |
| reporting | publication et distribution des rapports | trial balance et etats fournis | rapports metier/reglementaires | calcul metier comptable source |

Regle stricte V1:
- accounting est source de verite comptable
- tax, finance et reporting consomment des donnees publiees et versionnees par accounting

## 4. Agregats

Agregats racines V1:

- AccountAggregate
  - racine: Account
  - dimensions obligatoires: LegalEntityId, FiscalYear
- JournalEntryAggregate
  - racine: JournalEntry
  - enfants: JournalLine
  - dimensions obligatoires: LegalEntityId, FiscalYear, JournalCode
- PeriodCloseAggregate
  - racine: PeriodClose
  - dimensions obligatoires: LegalEntityId, FiscalYear

Projections derivees (non agregats transactionnels):
- LedgerProjection
- TrialBalanceProjection
- FinancialStatementsProjection

Regle transactionnelle V1:
- PostJournalEntry est atomique dans accounting
- la source de verite est le Journal
- Ledger et TrialBalance sont reconstruits de maniere deterministe depuis le Journal

## 5. Entites

Entites prioritaires V1:

- Account
  - attributs cle: legal_entity_id, fiscal_year, number, name, category, class_number, group_number, normal_balance, statement
- JournalEntry
  - attributs cle: legal_entity_id, fiscal_year, journal_code, reference, posting_date, status, posted_at
- JournalLine
  - attributs cle: account_id, side, amount, description
- PeriodClose
  - attributs cle: legal_entity_id, fiscal_year, period, status, closed_at, closed_by

Entites de projection:
- LedgerLine
- TrialBalanceLine
- StatementLine

## 6. Value Objects

Tous les montants utilisent Money base sur Decimal.

Value Objects communs:
- Money(amount: Decimal, currency: Currency)
- Currency(code: str ISO 3 lettres)
- Percentage(value: Decimal, intervalle [0,100])
- LegalEntityId(value: str)
- FiscalYear(value: int)
- AccountingPeriod(start_date, end_date)
- JournalCode(value: str)
- JournalReference(value: str)
- DebitCreditSide(DEBIT, CREDIT)

Regles absolues:
- interdiction des float
- egalite par valeur
- immutabilite systematique

## 7. Invariants metier

Invariants transverses:
- une JournalEntry est strictement equilibree: somme(debit) = somme(credit)
- une JournalEntry contient au moins 2 lignes
- une JournalEntry comptabilisee est append-only
- aucune suppression d'ecriture comptabilisee
- correction uniquement par contrepassation ou ecriture corrective tracable
- une periode cloturee est non modifiable
- les ecritures doivent etre datees dans une periode ouverte
- aggregation directe uniquement si devise identique

Unicite des references:
- reference unique par tuple (LegalEntityId, FiscalYear, JournalCode, JournalReference)

Invariants etats financiers:
- bilan: actifs = passifs + capitaux propres
- compte de resultat: resultat net = produits - charges

## 8. Services de domaine

Services de domaine V1:
- EntryBalancingService
  - verifie equilibre, cardinalite et coherence devise
- EntryPostingPolicy
  - verifie eligibilite de comptabilisation (periode, statut, unicite)
- CorrectionPolicy
  - applique les regles de contrepassation/ecriture corrective
- StatementComputationService
  - calcule les vues d'etats depuis la trial balance
- ClosingControlService
  - execute les controles pre-cloture

Regle:
- aucun service de domaine ne persiste ni ne depend de l'infrastructure

## 9. Repositories

Ports de domaine:

- AccountRepository
  - get_by_number, add, update, exists
- JournalEntryRepository
  - add, get_by_reference, mark_posted
- PeriodCloseRepository
  - get_by_period, close_period, reopen_period

Garanties obligatoires V1:
- idempotence des commandes sensibles (ex: PostJournalEntry)
- optimistic locking/version sur agregats transactionnels
- persistance atomique de JournalEntry + JournalLines
- contraintes d'unicite alignees sur (LegalEntityId, FiscalYear, JournalCode, JournalReference)

## 10. Cas d'utilisation

Commandes applicatives:
- CreateAccount
- UpdateAccountMetadata
- RecordJournalEntry
- PostJournalEntry
- ReverseJournalEntry
- OpenAccountingPeriod
- CloseAccountingPeriod
- ReopenAccountingPeriod

Requetes applicatives:
- GetLedgerByPeriod (projection)
- GetTrialBalance (projection)
- GetBalanceSheet (vue)
- GetIncomeStatement (vue)
- GetAuditTrail

Regles applicatives:
- orchestration uniquement
- validation metier deleguee au domaine
- dependances vers repositories uniquement via abstractions

## 11. Evenements de domaine

Evenements V1 internes accounting:
- JournalEntryRecorded
- JournalEntryPosted
- JournalEntryReversed
- AccountingPeriodClosed
- AccountingPeriodReopened

Conventions:
- evenement immutable
- horodatage UTC
- identifiant de correlation
- payload metier minimal

Note V1:
- ces evenements servent d'abord a la tracabilite interne
- pas de coherence eventual consistency imposee pour le coeur comptable V1

## 12. Regles de dependance entre couches

Regle Clean Architecture:
- Presentation -> Application
- Application -> Domain
- Infrastructure -> Application + Domain (implementation des ports)
- Domain -> Shared Kernel uniquement

Interdictions:
- Domain ne reference jamais ORM, HTTP, queue, fichiers, SDK externes
- Application ne reference jamais details SQL
- Infrastructure ne contient aucune regle metier

## 13. Responsabilite du Financial Statements Context

Le Financial Statements Context en V1:
- produit des vues calculees depuis la TrialBalance
- ne stocke aucun solde parallele source
- n'est pas source de verite transactionnelle
- applique des reclassements uniquement via regles documentees, versionnees et testees

## 14. Regles comptables suisses pertinentes V1

Exigences minimales V1:
- piste d'audit complete (qui, quoi, quand, pourquoi)
- intangibilite des ecritures comptabilisees
- conservation documentaire associee aux ecritures
- devise de tenue obligatoire par entite legale
- politique d'arrondis explicite et uniforme
- gestion stricte des periodes (ouvertes, cloturees)
- politique de correction par contrepassation/ecriture corrective tracable

Limites TVA V1:
- traitement TVA simple uniquement
- etiquetage fiscal explicite par ligne ou ecriture
- extraction d'assiettes sans moteur fiscal avance
- pas de cas complexes transfrontaliers en V1

## Conformité CO — exigences reportées sur l’infrastructure

Le noyau metier impose des invariants, mais la conformite operationnelle depend aussi de l'infrastructure.
Le systeme ne doit jamais presenter l'etat actuel comme "deja conforme" sans preuves d'exploitation.

Exigences a couvrir par les adapters de persistance et d'exploitation:
- inalterabilite des ecritures persistees (append-only pour les ecritures comptabilisees)
- absence de suppression silencieuse (suppression logique tracee ou interdite selon politique)
- piste d'audit persistee (qui, quoi, quand, pourquoi, correlation)
- conservation des documents relies aux ecritures selon la duree applicable
- horodatage fiable (UTC, source de temps maitrisee, derive controlee)
- integrite des pieces (empreintes, verification a la lecture, non-alteration)
- tracabilite des modifications de metadonnees (journal de changement versionne)
- controles d'acces (separation des roles, moindre privilege, revocation)
- sauvegarde et restauration testees (RPO/RTO definis et verifies)
- responsabilite explicite de l'infrastructure pour ces garanties hors domaine pur

References legales indicatives: art. 957a CO, art. 958f CO, Olico.
Pour chaque reference ci-dessus: A verifier sur le texte legal en vigueur avant toute communication client ou mise en production.

## 15. Hierarchie des erreurs metier

Chaque erreur metier expose:
- code stable
- categorie
- severite
- message utilisateur
- detail technique separe

Categories:
- VALIDATION
- INVARIANT
- CONCURRENCY
- PERIOD
- INTEGRITY

Exemples:
- ACC-VAL-001 / VALIDATION / HIGH / "Ecriture desequilibree" / detail technique debit-credit
- ACC-PER-001 / PERIOD / HIGH / "Periode cloturee" / detail technique periode
- ACC-INT-001 / INTEGRITY / HIGH / "Reference deja utilisee" / detail technique cle d'unicite

## 16. Strategie de tests

Pyramide de tests V1:
- domaine (majoritaire)
  - invariants d'agregats
  - services de domaine
  - value objects
- application
  - orchestration des cas d'utilisation avec repositories doubles
- contrats repositories
  - idempotence, verrou optimiste, atomicite
- integration
  - scenarios comptables critiques

Tests metier suisses prioritaires:
- ecriture equilibree
- contrepassation
- rejet modification periode cloturee
- report a nouveau
- TVA simple (base et controle etiquetage)
- multi-devise minimal (controle devise de tenue + conversion explicite)
- reconstruction deterministe du Ledger depuis le Journal

Regles qualite:
- tests deterministes
- horloge injectee via Clock
- aucun float dans les assertions monetaires

## 17. Ordre exact d'implementation par petites etapes

Etape 1
- implementer identifiants metier et periodes (LegalEntityId, FiscalYear, AccountingPeriod, JournalCode, JournalReference)
- tests unitaires complets de ces Value Objects

Etape 2
- implementer JournalEntry et JournalLine
- implementer RecordJournalEntry
- tests d'invariants journal (equilibre, cardinalite, devise)

Etape 3
- implementer PostJournalEntry atomique
- appliquer unicite reference par entite/exercice/journal
- tests d'idempotence et d'atomicite

Etape 4
- figer Journal append-only apres posting
- implementer correction par contrepassation/ecriture corrective
- tests d'immutabilite et de correction tracable

Etape 5
- implementer projections Ledger deterministes depuis Journal
- tests de reconstruction complete

Etape 6
- implementer TrialBalance projection
- tests de coherence debit/credit globale

Etape 7
- implementer vues Financial Statements depuis TrialBalance
- tests identites comptables et reclassements documentes

Etape 8
- implementer ouverture/cloture/reouverture de periode
- tests de verrouillage periode

Etape 9
- integrer contrats avec tax, finance, reporting
- tests de frontiere inter-contextes

## 18. Elements volontairement exclus de la premiere version

Exclus de V1:
- consolidation multi-entites juridiques
- moteur avance d'ecritures automatiques IA
- gestion avancee des immobilisations
- budget et forecast
- rapprochement bancaire automatique
- reporting reglementaire etendu
- facturation et paie
- optimisation fiscale automatisee
- TVA complexe (cas transfrontaliers, regimes specifiques avances)

Ces sujets seront traites dans des increments ulterieurs apres stabilisation du coeur comptable V1.
