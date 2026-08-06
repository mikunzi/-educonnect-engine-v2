# Accounting Persistence Architecture
## 1. Statut du document
- Version: 1.0.0
- Phase concernée: Phase 7.1
- Statut: architecture cible, non implémentée
- Portée: cadrage de la couche de persistance du bounded context Accounting
- Date: 2026-08-06
- Source de vérité:
  - Contrats métier existants dans src/educonnect_engine/accounting/domain/repositories.py
  - Agrégats métier dans src/educonnect_engine/accounting/domain
  - Cas d’utilisation applicatifs dans src/educonnect_engine/accounting/application
  - Décisions d’architecture du dépôt dans docs/architecture/ACCOUNTING_BLUEPRINT.md
Ce document décrit une architecture de persistance cible.
Ce document ne constitue pas une preuve d’implémentation.
Ce document ne constitue pas une preuve de conformité légale.
Ce document ne crée aucun engagement de performance en production.
Ce document doit être relu et validé avant toute implémentation technique.
## 2. Mission
La mission de la Phase 7 est de préparer une persistance durable pour Accounting sans altérer le modèle métier.
La persistance doit:
- conserver les agrégats comptables;
- préserver les invariants définis dans le domaine;
- maintenir l’immutabilité logique des transitions métier;
- garantir l’atomicité des opérations applicatives critiques;
- supporter la concurrence optimiste;
- rester compatible avec les ports de repositories existants.
La mission ne couvre pas:
- l’écriture de SQL exécutable;
- l’ajout de code Python de repository concret;
- l’installation de dépendances externes;
- la migration de données existantes;
- l’exposition API;
- la validation réglementaire finale.
Objectif d’architecture:
- définir un cadre stable pour les futures PR 7.2 à 7.7;
- éviter les dérives de dépendance;
- éviter l’introduction de logique métier dans l’infrastructure;
- préparer des décisions techniques traçables.
## 3. Principes structurants
### 3.1 DDD
- Le domaine est propriétaire des règles métier et des invariants.
- Les agrégats représentent les frontières de cohérence transactionnelle.
- Les value objects garantissent la validité des valeurs par construction.
- Les repositories sont des ports métier, pas des détails SQL.
### 3.2 Clean Architecture
- Le domaine ne dépend d’aucun framework de persistance.
- L’application orchestre des cas d’usage, sans SQL.
- L’infrastructure implémente les ports et traduit les détails techniques.
- Les dépendances pointent vers l’intérieur.
### 3.3 Dependency Rule
Sens strict attendu:
- Domain
- Application dépend du Domain
- Infrastructure dépend du Domain et de l’Application
Conséquence:
- aucune importation sqlite3 dans le domain;
- aucune importation sqlite3 dans l’application;
- aucune importation de module infrastructure dans le domain;
- aucune importation de module infrastructure dans l’application.
### 3.4 Ports and Adapters
- Les ports de repositories sont définis côté métier.
- Les adapters SQL sont définis côté infrastructure.
- Les adapters se conforment exactement aux signatures des ports existants.
- Les adapters ne modifient pas les contrats métier.
### 3.5 Repository Pattern
- Le repository fournit l’accès persistant aux agrégats.
- Le repository n’embarque pas de logique de décision métier.
- Le repository traduit les erreurs techniques en erreurs de persistance compréhensibles.
- Le repository préserve les invariants via reconstruction valide.
### 3.6 Unit of Work
- Le Unit of Work définit la frontière transactionnelle d’un cas d’usage.
- Une commande applicative sensible s’exécute dans une seule transaction atomique.
- Le Unit of Work orchestre commit, rollback, fermeture des ressources.
### 3.7 Mapping explicite
- Le mapping Domain vers Persistence est explicite et testable.
- Le mapping Persistence vers Domain reconstruit les agrégats sans contournement.
- Le mapping n’accède pas à la base de données.
### 3.8 Transactions atomiques
- Une écriture d’agrégat composite ne doit jamais être partielle.
- Les entêtes et lignes comptables doivent être persistés ensemble.
- Un échec de validation ou de commit annule toute mutation.
### 3.9 Concurrence optimiste
- Les agrégats versionnés utilisent une colonne de version persistée.
- La mise à jour conditionnelle doit vérifier id et version attendue.
- Un conflit de version remonte une erreur métier-applicative contrôlée.
## 4. Règles absolues
- Aucun import sqlite3 dans domain.
- Aucun import sqlite3 dans application.
- Aucun SQL dans domain.
- Aucun SQL dans application.
- Aucune logique métier dans les repositories SQL.
- Aucune mutation silencieuse d’un agrégat.
- Aucun contournement des constructeurs ou invariants d’agrégat.
- Aucune suppression silencieuse d’une écriture comptabilisée.
- Aucun stockage principal des agrégats comptables sous blob JSON opaque.
- Aucune dépendance d’un port métier vers l’infrastructure.
- Aucune modification des signatures des ports existants en Phase 7.1.
- Aucune affirmation que la conformité légale est déjà acquise.
- Aucune affirmation que la persistance est déjà en place.
Règle de formulation documentaire:
- utiliser les verbes cibler, prévoir, recommander, proposer;
- éviter les verbes implémenter, est en production, est conforme;
- conserver la distinction entre cible et état courant.
## 5. Architecture cible
Arborescence cible future:
src/educonnect_engine/accounting/
    domain/
    application/
    infrastructure/
        persistence/
            README.md
            exceptions.py
            unit_of_work.py
            sqlite/
                __init__.py
                connection_factory.py
                schema/
                    migrations/
                repositories/
                mappers/
Interprétation de cette arborescence:
- persistence isole les aspects techniques de persistance;
- sqlite contient l’implémentation initiale ciblée;
- schema/migrations organise les scripts SQL versionnés;
- repositories contient les adapters conformes aux ports métier;
- mappers contient les traducteurs Domain et Persistence;
- exceptions porte la taxonomie d’erreurs de persistance;
- unit_of_work porte le contrat et l’implémentation SQL UoW.
Précision importante:
- cette arborescence est une cible;
- cette PR ne crée pas cette arborescence;
- cette PR ne crée aucun fichier sous src.
## 6. Flux de dépendances
Flux d’écriture cible:
- Application Service
- vers Repository Port
- vers SQL Adapter
- vers Mapper
- vers SQLite
Flux de lecture cible:
- SQLite
- vers Mapper
- vers Aggregate Domain
- vers Application Service
Explication:
- Les ports sont définis côté métier.
- Les implémentations sont fournies côté infrastructure.
- L’application ne connaît que les ports.
- Le domaine ne connaît ni SQL ni SQLite.
Conséquences de design:
- Les cas d’usage conservent leur signature actuelle.
- Les injections de dépendances ciblent des interfaces métier.
- Les modules infrastructure restent remplaçables.
## 7. Agrégats persistables
### 7.1 JournalEntry
- Rôle: écriture comptable à partie double avec lignes équilibrées.
- Identifiant: JournalEntryId.
- Version: entier de version déjà présent dans l’agrégat.
- Priorité de persistance: maximale.
- Invariants critiques:
  - minimum deux lignes;
  - devise unique sur toutes les lignes;
  - total débit égal total crédit;
  - cohérence status et posted_at;
  - cohérence correction_of_entry_id et correction_reason.
- Relations:
  - compose plusieurs JournalLine;
  - peut référencer une écriture source via correction_of_entry_id.
- Niveau de priorité MVP: P1.
### 7.2 Account
- Rôle: structure du plan comptable et classification fonctionnelle.
- Identifiant: numéro de compte fonctionnel.
- Version: non versionné à ce stade dans la structure actuelle.
- Priorité de persistance: moyenne.
- Invariants critiques:
  - number positif;
  - name non vide;
  - class_number et group_number positifs.
- Relations:
  - utilisé par les lignes d’écriture pour account_number.
- Niveau de priorité MVP: P2.
### 7.3 AccountingPeriod
- Rôle: borne temporelle de saisie comptable et statut de cycle.
- Identifiant: AccountingPeriodId.
- Version: entier de version déjà présent.
- Priorité de persistance: élevée.
- Invariants critiques:
  - dates compatibles avec fiscal year;
  - start_date inférieur ou égal à end_date;
  - transitions OPEN vers CLOSED puis CLOSED vers LOCKED;
  - contrôle de version attendu sur transitions.
- Relations:
  - liée au scope legal_entity_id et fiscal_year.
- Niveau de priorité MVP: P1.
### 7.4 FiscalYearClosing
- Rôle: état de clôture annuelle et horodatage de clôture.
- Identifiant: FiscalYearClosingId.
- Version: entier de version déjà présent.
- Priorité de persistance: élevée.
- Invariants critiques:
  - OPEN sans closing_timestamp;
  - CLOSED avec closing_timestamp;
  - transition OPEN vers CLOSED uniquement.
- Relations:
  - dépend de prérequis de cohérence de période et états financiers.
- Niveau de priorité MVP: P2.
### 7.5 YearEndSnapshot
- Rôle: capture immutable de projection annuelle cohérente.
- Identifiant: YearEndSnapshotId.
- Version: source_version présent.
- Priorité de persistance: moyenne à élevée.
- Invariants critiques:
  - scope homogène entre trial balance et états financiers;
  - devise homogène;
  - captured_at strictement UTC;
  - source_version non négatif.
- Relations:
  - encapsule TrialBalance et FinancialStatements.
- Niveau de priorité MVP: P2.
### 7.6 OpeningEntry
- Rôle: entrée d’ouverture dérivée d’un snapshot de fin d’exercice.
- Identifiant: clé fonctionnelle basée sur source_snapshot_id.
- Version: entier de version déjà présent.
- Priorité de persistance: moyenne.
- Invariants critiques:
  - fiscal_year cible égal fiscal_year source plus un;
  - date de comptabilisation au premier jour de l’année cible;
  - cohérence status opening entry et status journal entry;
  - contrôle de version sur transition GENERATED vers POSTED.
- Relations:
  - référence YearEndSnapshot;
  - contient un JournalEntry.
- Niveau de priorité MVP: P3.
### 7.7 Tranche verticale recommandée
- Première tranche verticale recommandée: JournalEntry.
Raison:
- centralité métier;
- existence d’invariants forts;
- dépendance directe de plusieurs cas d’usage;
- valeur démonstrative élevée pour mapper, repository, UoW et concurrence optimiste.
## 8. Repository Pattern
Responsabilités autorisées:
- persister un agrégat valide;
- relire un agrégat par identifiant;
- appliquer des contraintes techniques d’unicité et d’intégrité;
- gérer la version de concurrence optimiste;
- traduire les exceptions techniques en erreurs de persistance;
- retourner des objets domaine reconstruits.
Responsabilités interdites:
- décider des transitions métier;
- recalculer des règles d’équilibrage métier;
- injecter des valeurs métier non fournies;
- contourner les constructeurs de domaine;
- opérer des suppressions non prévues par le métier;
- exposer des objets SQL bruts au domaine.
Récupération par identifiant:
- via méthodes existantes get_by_id sur ports concernés;
- retourne agrégat ou null selon contrat existant;
- absence d’invention de nouvelle méthode de requête en 7.1.
Sauvegarde:
- via add, save, save_posted, save_reversal selon port;
- agrégats écrits avec validation de version si requis;
- aucune mutation implicite hors transition métier explicite.
Détection des doublons:
- contrainte technique en persistance;
- remontée en DuplicateEntityError côté adapter;
- aucun fallback silencieux.
Gestion des versions:
- version persistée en entier positif;
- update conditionné par version attendue;
- conflit remonté en OptimisticConcurrencyError.
Absence de logique métier:
- le repository ne décide pas qu’une période est ouverte;
- le repository ne décide pas qu’une écriture est postable;
- le repository applique uniquement les contrats et contraintes de stockage.
Traduction des erreurs techniques:
- conversion des erreurs SQLite en taxonomie de persistance;
- conservation d’informations de diagnostic non sensibles;
- interdiction de fuite d’erreurs driver brutes vers les couches métier.
Compatibilité des méthodes avec ports existants:
- JournalEntryRepository.add
- JournalEntryRepository.get_by_id
- JournalEntryRepository.save_posted
- JournalEntryRepository.save_reversal
- AccountingPeriodRepository.is_open
- AccountingPeriodLifecycleRepository.get_by_id
- AccountingPeriodLifecycleRepository.add
- AccountingPeriodLifecycleRepository.save
- AccountingPeriodLifecycleRepository.has_open_period
- AccountingPeriodLifecycleRepository.has_overlapping_period
- FiscalYearClosingRepository.get_by_id
- FiscalYearClosingRepository.exists_closed
- FiscalYearClosingRepository.save_closed
- FiscalYearClosingPrerequisiteRepository.are_all_periods_locked
- FiscalYearClosingPrerequisiteRepository.has_recorded_journal_entries
- FiscalYearClosingPrerequisiteRepository.has_posting_or_reversal_in_progress
- FiscalYearClosingPrerequisiteRepository.has_coherent_balanced_financial_statements
- YearEndSnapshotSourceRepository.get_consistent_source
- YearEndSnapshotRepository.get_by_id
- YearEndSnapshotRepository.get_by_scope
- YearEndSnapshotRepository.add
- YearEndSnapshotPrerequisiteRepository.has_recorded_journal_entries
- YearEndSnapshotPrerequisiteRepository.has_posting_or_reversal_in_progress
- YearEndSnapshotPrerequisiteRepository.is_fiscal_year_closed
- OpeningEntryRepository.exists_for_snapshot
- OpeningEntryRepository.add
- IdempotencyRepository.get
- IdempotencyRepository.save
## 9. Unit of Work
Contrat cible futur:
- ouverture de contexte;
- début de transaction;
- repositories exposés dans le périmètre de transaction;
- commit en sortie nominale;
- rollback en cas d’exception;
- fermeture de ressources en sortie.
Comportement context manager:
- entrée: initialise le contexte transactionnel;
- sortie sans erreur: commit;
- sortie avec erreur: rollback automatique;
- sortie finale: fermeture de la connexion ou libération de session.
Règles opérationnelles:
- une opération métier applicative doit être atomique;
- un cas d’usage modifiant des agrégats ne doit pas ouvrir plusieurs transactions indépendantes;
- un repository ne doit pas commiter seul;
- après fermeture du Unit of Work, un repository lié au contexte fermé devient invalide;
- tentative d’usage post-fermeture doit provoquer une erreur explicite.
Intégration avec ports actuels:
- le domaine expose déjà transaction comme contexte abstrait;
- l’infrastructure future devra respecter ce contrat sans extension métier additionnelle.
## 10. Mapping domaine vers SQL
Responsabilités du mapper:
- conversion Domain vers Persistence;
- conversion Persistence vers Domain;
- validation structurelle des valeurs lues;
- conservation stricte de l’ordre des lignes;
- reconstruction des agrégats via constructeurs et invariants du domaine.
Contraintes du mapper:
- aucun accès direct à la base de données;
- aucune logique de décision métier;
- aucun recalcul de règles métiers;
- aucune correction silencieuse des données invalides;
- aucune suppression de champ sans stratégie explicite.
Exigences de reconstruction:
- les value objects doivent être reconstruits explicitement;
- les enums doivent être réhydratés depuis des représentations stables;
- les timestamps doivent être vérifiés sur UTC quand requis;
- un enregistrement incohérent doit remonter MappingError.
Politique de validation:
- validation métier finale déléguée aux constructeurs de domaine;
- validation technique de format réalisée côté mapper;
- rejet explicite des données incompatibles.
## 11. Conventions de représentation
Les conventions suivantes sont cibles pour les futures PR.
Certaines décisions restent ouvertes et doivent être validées avant implémentation.
### 11.1 UUID
- Représentation textuelle canonique.
- Stable entre lectures et écritures.
- Comparaison exacte sans normalisation implicite cachée.
### 11.2 Decimal et Money
Option cible à valider avant implémentation:
- stockage en unités mineures entières; ou
- stockage décimal exact sous représentation textuelle contrôlée.
Décision finale non arrêtée dans cette PR.
### 11.3 Currency
- Code ISO structurel.
- Valeur textuelle stable.
- Validation par value object métier.
### 11.4 Dates
- Format ISO.
- Cohérence avec fiscal year selon agrégat.
### 11.5 Datetimes
- UTC obligatoire lorsque le domaine l’exige.
- Format canonique stable à valider.
Décision finale de format de stockage non arrêtée dans cette PR.
### 11.6 Enum
- Valeur textuelle stable.
- Pas de codage implicite dépendant d’un ordinal.
### 11.7 Booléens SQLite
- Représentation explicite cible.
- Convention exacte à formaliser avant implémentation.
### 11.8 Ordre des lignes
- Position entière explicite.
- Ordre strictement conservé à la relecture.
### 11.9 Version
- Entier positif ou nul selon invariant d’agrégat.
- Incrément strict lors des transitions prévues.
## 12. Modèle relationnel cible du JournalEntry
Schéma documentaire proposé.
Schéma non implémenté dans cette PR.
### 12.1 Table journal_entries
Colonnes minimales proposées:
- id
- entry_number
- posting_date
- description
- status
- currency
- version
- source_entry_id nullable
- correction_reason nullable
- created_at
- updated_at
Clés et contraintes proposées:
- clé primaire sur id;
- contrainte d’unicité métier sur le numéro d’écriture dans son scope;
- clé étrangère source_entry_id vers journal_entries.id;
- cohérence nullable entre source_entry_id et correction_reason;
- contrainte de version non négative;
- contrainte status sur liste stable de valeurs.
Index utiles proposés:
- index sur posting_date;
- index sur status;
- index sur source_entry_id;
- index sur combinaison de scope métier.
### 12.2 Table journal_entry_lines
Colonnes minimales proposées:
- entry_id
- position
- account_number
- debit_amount
- credit_amount
- currency
- description nullable
Clés et contraintes proposées:
- clé primaire composite sur entry_id et position;
- clé étrangère entry_id vers journal_entries.id;
- contrainte de montant autorisant zéro sur un seul côté par ligne;
- contrainte interdisant débit et crédit strictement positifs simultanément;
- contrainte de devise cohérente au niveau ligne.
Ordre des lignes:
- position entière obligatoire;
- ordre de reconstruction basé sur position croissante;
- absence de position dupliquée pour une même écriture.
Suppression en cascade:
- stratégie à décider avant implémentation;
- si suppression logique interdite pour écritures comptabilisées, la suppression physique doit être strictement contrôlée;
- la politique finale doit préserver inaltérabilité et auditabilité.
Caractère non implémenté:
- ce schéma est une proposition de conception;
- aucune table n’est créée par cette PR.
## 13. Transactions et atomicité
Principe directeur:
- une transaction par cas d’utilisation applicatif mutateur.
Règles cibles:
- insertion de l’en-tête et des lignes dans la même transaction;
- rollback complet en cas d’échec;
- propagation contrôlée des erreurs vers l’application;
- aucune écriture partielle tolérée;
- commit explicite en sortie nominale.
Comportement en cas d’échec du commit:
- transaction considérée échouée;
- état final traité comme non validé;
- erreur technique traduite en TransactionError ou RepositoryError;
- aucun succès métier ne doit être signalé.
Garantie attendue:
- soit l’opération métier est entièrement persistée;
- soit aucune mutation durable n’est conservée.
## 14. Concurrence optimiste
Principe cible:
- mise à jour conditionnée par id et version attendue.
Formulation de principe:
- UPDATE ... WHERE id = ? AND version = ?
Règle de résultat:
- le nombre de lignes modifiées doit être exactement 1.
Sinon:
- remonter une erreur de concurrence optimiste.
Portée:
- JournalEntry versionné;
- AccountingPeriod versionné;
- FiscalYearClosing versionné;
- OpeningEntry versionné;
- tout autre agrégat versionné explicitement.
Limites de cette PR:
- aucun SQL complet n’est fourni;
- seul le principe est fixé.
## 15. Idempotence
Objectif:
- éviter les doubles effets sur commandes répétées.
Éléments cibles:
- clé d’idempotence;
- portée de clé clairement définie;
- résultat typé persistant;
- détection des répétitions;
- politique de replay déterministe.
Contraintes:
- pas de blob opaque principal pour données comptables;
- séparation nette entre logique applicative et stockage technique;
- aucune décision métier portée par la table d’idempotence.
Politique de replay recommandée:
- si clé connue et succès enregistré, renvoyer résultat canonique;
- si clé connue et échec terminal enregistré, stratégie à valider;
- si clé inconnue, exécuter flux normal.
Point de décision différée:
- le contrat exact d’idempotence doit être confirmé en PR future.
## 16. Migrations
Décisions structurantes:
- scripts SQL versionnés;
- migrations ordonnées;
- table de version de schéma;
- transaction de migration lorsque SQLite le permet;
- aucune dépendance Alembic en première version;
- migrations ascendantes obligatoires.
Rollback:
- stratégie de rollback documentée;
- automatisation potentiellement différée;
- priorité initiale sur robustesse des migrations forward.
Exigences de gouvernance:
- chaque migration doit être traçable;
- chaque migration doit préciser préconditions et postconditions;
- chaque migration doit être testée en environnement isolé.
## 17. Erreurs de persistance
Taxonomie cible sans implémentation:
- PersistenceError
- RepositoryError
- DuplicateEntityError
- EntityNotFoundError
- OptimisticConcurrencyError
- TransactionError
- MappingError
- SchemaVersionError
Règle de traduction:
- les erreurs techniques SQLite sont capturées dans l’infrastructure;
- elles sont traduites vers la taxonomie cible;
- les couches application et domain ne manipulent pas des erreurs driver brutes.
Règle de journalisation:
- conserver contexte technique utile;
- exclure données sensibles;
- éviter fuite de détails de stockage côté métier.
## 18. Tests attendus
Tests futurs attendus:
- sauvegarde et relecture d’agrégat;
- conservation exacte des lignes;
- conservation stricte de l’ordre des lignes;
- rollback sur erreur;
- atomicité entête et lignes;
- détection de doublon;
- récupération d’identifiant inconnu;
- conflit de version;
- flux d’extourne;
- fermeture puis réouverture de la base;
- application des migrations;
- contrainte de clé étrangère;
- absence d’import SQL dans domain et application;
- reconstruction fidèle des agrégats.
Tests d’architecture:
- vérification automatique de dépendances interdites;
- vérification absence SQL hors infrastructure;
- vérification conformité des adapters aux ports.
Tests de non-régression:
- cas d’usage applicatifs existants restent fonctionnels;
- invariants métier inchangés;
- aucun changement de contrat public non validé.
## 19. Sécurité
Principes cibles:
- requêtes paramétrées;
- aucune concaténation SQL dynamique non maîtrisée;
- permissions minimales sur fichiers et répertoires;
- protection des fichiers SQLite;
- absence de données sensibles en logs;
- intégrité des migrations;
- stratégie de sauvegarde;
- stratégie de restauration;
- chiffrement différé selon contexte de déploiement.
Important:
- aucune affirmation de conformité acquise;
- sécurité réelle à valider sur implémentation, exploitation et configuration.
## 20. Conformité comptable et légale
Axes à couvrir dans la future implémentation:
- inaltérabilité des écritures comptabilisées;
- traçabilité des opérations;
- piste d’audit exploitable;
- conservation documentaire;
- intégrité des pièces comptables;
- horodatage fiable.
Mention obligatoire:
À vérifier sur les textes légaux en vigueur avant toute communication client ou mise en production.
Précision:
- ce document n’atteste pas la conformité.
## 21. Performance
Lignes directrices:
- index ciblés sur clés de lecture fréquentes;
- pagination sur requêtes volumineuses;
- éviter les patterns N+1;
- charger un agrégat complet quand la cohérence métier l’exige;
- garder des transactions courtes;
- mesurer avant optimiser.
Positionnement technologique:
- SQLite est adapté au MVP de persistance locale ou contrôlée;
- SQLite n’est pas supposé adapté à tous les déploiements futurs;
- l’architecture doit rester portable vers un moteur relationnel plus robuste.
## 22. Observabilité
Observabilité cible:
- logs techniques sans données sensibles;
- durée des transactions;
- nombre de rollbacks;
- nombre d’erreurs de concurrence;
- version de schéma active;
- métriques futures de latence et taux d’échec.
Règles:
- corrélation des événements techniques d’une même transaction;
- séparation journalisation métier et journalisation technique;
- pas d’exposition d’informations sensibles dans les erreurs externes.
## 23. Évolution future
Trajectoire possible:
- SQLite
- vers PostgreSQL
- vers exposition API
- vers services distribués éventuels
Principe de stabilité:
- le domain reste stable;
- les ports restent stables;
- l’infrastructure change sans casser les contrats métier.
Préparation:
- éviter les choix non portables inutiles;
- garder les mappers explicites;
- isoler les détails de dialecte SQL dans l’adapter.
## 24. Plan des Pull Requests
### PR 7.2
- Objectif: connection factory SQLite et bootstrap d’infrastructure.
- Périmètre:
  - création de l’arborescence persistence cible;
  - connection_factory;
  - bases de gestion d’erreurs techniques;
  - préparation du Unit of Work technique.
- Tests:
  - ouverture et fermeture de connexion;
  - validations d’architecture sur dépendances;
  - absence d’import sqlite3 en domain et application.
- Critères d’acceptation:
  - structure de persistance créée;
  - aucune logique métier déplacée;
  - quality gates verts.
### PR 7.3
- Objectif: migrations et schéma initial.
- Périmètre:
  - scripts SQL versionnés;
  - table de version de schéma;
  - procédure d’application ordonnée.
- Tests:
  - migration sur base vide;
  - relecture version de schéma;
  - migration idempotente selon stratégie retenue.
- Critères d’acceptation:
  - schéma initial généré;
  - mécanisme de version traçable;
  - quality gates verts.
### PR 7.4
- Objectif: mapper JournalEntry et repository associé.
- Périmètre:
  - mapping Domain vers Persistence;
  - mapping Persistence vers Domain;
  - adapter JournalEntryRepository.
- Tests:
  - round trip d’agrégat;
  - conservation ordre des lignes;
  - doublon;
  - identifiant inconnu.
- Critères d’acceptation:
  - conformité au port existant;
  - invariants préservés;
  - quality gates verts.
### PR 7.5
- Objectif: SQL Unit of Work et transactions.
- Périmètre:
  - implémentation UoW context manager;
  - commit et rollback;
  - cohérence transactionnelle sur cas d’usage mutateurs.
- Tests:
  - rollback automatique sur exception;
  - atomicité entête et lignes;
  - échec de commit.
- Critères d’acceptation:
  - opérations atomiques;
  - aucun commit partiel;
  - quality gates verts.
### PR 7.6
- Objectif: AccountingPeriod et snapshots.
- Périmètre:
  - adapters des repositories de période;
  - adapters des snapshots et prérequis associés;
  - prise en charge de la concurrence optimiste concernée.
- Tests:
  - is_open;
  - transitions de période;
  - cohérence source snapshot.
- Critères d’acceptation:
  - ports couverts sans dérive;
  - invariants préservés;
  - quality gates verts.
### PR 7.7
- Objectif: tests d’intégration, documentation et durcissement.
- Périmètre:
  - suite intégration complète;
  - durcissement erreurs et observabilité;
  - documentation opératoire des migrations.
- Tests:
  - scénario bout en bout prioritaire;
  - contrainte de clé étrangère;
  - fermeture réouverture base;
  - vérification architecture et imports.
- Critères d’acceptation:
  - couverture des cas critiques;
  - documentation alignée;
  - quality gates verts.
## 25. Checklist de revue
- Domaine inchangé.
- Application indépendante de SQLite.
- SQL paramétré.
- Transaction explicite.
- Rollback testé.
- Concurrence testée.
- Mapping testé.
- Migrations versionnées.
- Aucune dépendance interdite.
- Quality gates verts.
- Documentation mise à jour.
Checklist complémentaire recommandée:
- Contrats des ports inchangés.
- Taxonomie d’erreurs appliquée.
- Aucune fuite de détail SQLite vers application.
- Aucune fuite de détail SQLite vers domain.
- Politique d’idempotence documentée.
- Aucune affirmation de conformité légale acquise.
## 26. Décisions différées
Décisions à finaliser avant implémentation complète:
- représentation finale des montants;
- format exact de stockage des datetimes;
- contrat exact d’idempotence;
- niveau de support PostgreSQL;
- politique de chiffrement;
- stratégie de sauvegarde;
- politique de suppression logique;
- exigences de charge.
Cadre de décision:
- décision documentée;
- justification métier et technique;
- impact sur ports évalué;
- impact migration évalué;
- validation humaine obligatoire.
## 27. Definition of Done de la Phase 7
La Phase 7 est terminée quand les conditions suivantes sont toutes satisfaites:
- persistance réelle implémentée pour les agrégats prioritaires;
- transactions atomiques opérationnelles;
- migrations versionnées opérationnelles;
- repositories prioritaires livrés;
- concurrence optimiste couverte;
- tests d’intégration critiques verts;
- architecture protégée par tests de dépendances;
- documentation technique à jour;
- quality gates verts;
- aucune régression du Core.
Critères de clôture détaillés:
- les cas d’usage mutateurs critiques ne produisent pas d’écritures partielles;
- les conflits de version remontent des erreurs déterministes;
- les mappings reconstruisent les agrégats sans contournement;
- l’infrastructure respecte strictement les ports métier existants;
- le domain et l’application restent indépendants de SQLite;
- la stratégie de migration est testée et traçable;
- la taxonomie d’erreurs de persistance est appliquée de manière cohérente;
- les preuves de tests sont disponibles dans la CI.
Clause finale:
- ce document définit une cible d’architecture;
- il ne doit pas être interprété comme une implémentation déjà livrée.
