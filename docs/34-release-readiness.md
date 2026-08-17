# 34 — AIEF Release Readiness

Audit de consolidation exécuté après : le correctif de scoping de l'Effective
Engineering Context, l'observabilité légère du Runtime, et le harness
d'évaluation à 3 niveaux. Toute affirmation ci-dessous est adossée à une
commande réellement exécutée dans cette session (`pytest`, ou un appel direct
au harness) — pas à une relecture de code seule.

**État de la suite au moment de cet audit : 192 tests passent, 3 échouent.**
Les 3 échecs sont connus, diagnostiqués, et non liés au code Runtime :
- `test_organization_catalog_selection_changes_effective_practices` et
  `test_package_is_valid` — bloqués par le sous-module git privé
  `organization/catalogs/gad-guidelines` (`gitlab.com/Gad-Digital-IT/shared/guidelines.git`),
  injoignable dans cet environnement (tentative de `git submodule update
  --init` restée bloquée sur la résolution réseau).
- `test_gitlab_native_provider_exposes_only_verified_task_operations` —
  fixture de test Codex/GitLab obsolète, sans rapport avec le Runtime.

Une simplification a été appliquée pendant cet audit : les événements
`validation.completed`/`validation.failed` dupliquaient exactement
`phase.completed`/`phase.failed`+`execution.*` (même transition, même
payload, deux noms). Supprimés ; aucun test n'en dépendait. Un test manquant
a aussi été comblé : `Execution.cancel()`/`execution.cancelled` n'avait
aucun test dédié avant cet audit — ajouté (`test_cancel_execution_reaches_the_declared_cancelled_status_and_emits_its_event`).

---

## 1. Functional scope

Runtime déterministe partagé par Claude Code et Codex : intake (Request →
IntentResolution → Task), compilation de workflow, exécution par phases,
policy dynamique, gates, tracking externe, sécurité de workspace,
résolution de contexte d'ingénierie effectif, journal d'événements
structuré, et un harness de conformité à 3 niveaux. Le raisonnement
sémantique et la production de code restent entièrement du ressort de
l'agent — AIEF ne génère et n'évalue aucun code.

## 2. Runtime guarantees — preuves

| Garantie | Preuve exécutée |
|---|---|
| Transitions déterministes | `tests/test_runtime.py`, `tests/test_service.py` (191 assertions passantes sur les transitions de phase/Execution) |
| Idempotence | `tests/test_concurrency.py` (replay d'opération) ; `tests/test_scenarios.py::test_scenarios_are_reproducible_across_independent_runs` (même scénario, deux exécutions indépendantes, résultat identique) |
| Resume | `tests/test_observability.py::test_workspace_events_after_resume_show_blocked_then_prepared` (blocage puis reprise, vérifié à la fois sur l'état et sur l'événement) |
| Error handling | `run_profile_validation` échoue fermé (`phase.failed`+`execution.failed`, sans fallback) ; `tests/test_scenarios.py` scénario `missing-provider` |
| Execution state | schéma `execution.schema.json` validé sur chaque Execution créée dans la suite ; `cancelledReason` ajouté et schema-validé |
| Task revisions | `PolicyDecision` versionnée (`policy-decision-NNN.yaml`), `tests/test_dynamic_policy.py::test_runtime_reassesses_after_impact_and_plan_and_never_lowers_risk` — le risque ne redescend jamais silencieusement |
| Gates | `tests/test_observability.py::test_gate_lifecycle_emits_requested_then_approved` ; `tests/test_scenarios.py` scénario `human-gate` |
| Tracking | `tests/test_tracking.py` ; `tests/test_scenarios.py` scénario `tracking-required` |
| Workspace safety | `tests/test_workspace.py` ; `tests/test_scenarios.py` scénario `dirty-workspace` |

Point d'attention corrigé cette session : la résolution de contexte
échouait pour **tout** projet dès qu'**un** document de pratique
organisationnelle, n'importe où dans l'arbre `organization/`, était
manquant — même sans rapport avec le projet résolu. Corrigé
(`aief/engineering.py`), régression-gardé par
`tests/test_engineering.py::test_missing_document_in_unreferenced_catalog_does_not_break_a_referenced_sibling`.

## 3. Agent guarantees — preuves

Exécution réelle du harness Level 2 sur 4 scénarios représentatifs, `claude-code` vs `codex` :

```text
Scenario           Expected                                        Observed   Status
simple-feature     identical trajectory for claude-code and codex  identical  PASS
human-gate         identical trajectory for claude-code and codex  identical  PASS
tracking-required  identical trajectory for claude-code and codex  identical  PASS
dirty-workspace    identical trajectory for claude-code and codex  identical  PASS
```

Les 12 scénarios du harness passent en Level 2 dans la suite complète
(`tests/test_scenarios.py::test_level2_adapter_conformance_scenario_passes`,
12/12). Même Task normalisée, même Workflow compilé, même PolicyDecision,
même Effective Engineering Context (`resolve_engineering_context` n'a
aucun paramètre `agent`), mêmes gates franchis — vérifié mécaniquement, pas
supposé.

`git diff --stat main -- adapters/` est vide pour toute cette série
d'incréments : aucune logique n'a été ajoutée dans les adapters. Les deux
adapters restent structurellement identiques (mêmes 8 workflows, mêmes 14
skills mappés vers les mêmes fichiers Core), seule la syntaxe d'invocation
diffère (`/implement` vs `$implement`) — c'est la seule différence
« réellement agentique » constatée au niveau du Runtime ; la qualité du
raisonnement et du code produit reste, par principe, hors du périmètre
vérifiable par AIEF (Level 3).

## 4. Governance guarantees — preuves

- Mandatory : `tests/test_engineering.py::test_mandatory_practice_cannot_be_disabled_or_overridden`, `test_task_cannot_override_mandatory_organization_practice`. Scénario harness `policy-conflict`.
- Default + override autorisé, tracé : `test_project_can_override_an_allowed_default_and_resolution_is_traced`. Scénario harness `organization-practice-override`.
- Isolation par catalogue référencé (le correctif de cette série) :
  `test_missing_document_in_unreferenced_catalog_does_not_break_a_referenced_sibling`.
- Chargement progressif par catégorie de Skill : `test_progressive_loading_returns_no_practices_for_skill_without_requested_categories`,
  `test_impact_analysis_loads_architecture_and_security_but_not_review_or_testing`.
- Provenance et fingerprint stables : `test_context_has_stable_fingerprint_and_document_provenance`.
- **Limite non résolue** : la majorité des fichiers de policy hors
  risk/autonomy/human-approval (`change-policy`, `context-policy`,
  `external-action-policy`, `traceability-policy`, `recovery-policy`,
  `memory-policy`, `source-control-identity-policy`) ne sont chargés par
  aucun code Python — gouvernance documentée, non appliquée. Non corrigé
  dans cette série (hors périmètre des incréments demandés) ; à traiter
  avant de présenter ces politiques comme actives à une organisation
  pilote.

## 5. Compatibility — preuves

| Cas | Preuve |
|---|---|
| Projet existant | Toute la suite (192 tests) tourne contre `templates/project` sans modification de contrat |
| Monorepo | `workspace.strategy: monorepo` est la valeur **par défaut** de `templates/project` — exercée implicitement par la quasi-totalité de la suite, y compris les 12 scénarios du harness |
| Polyrepo | `examples/emmany` (`workspace.strategy: polyrepo`, 2 dépôts) ; scénario harness `multi-repo-change` ; `tests/test_workspace.py` (blocage poly-repo si un dépôt est sale) |
| Java/Spring | `examples/emmany` repository `egw-api` (profils `java`+`spring`+`maven`) ; `test_java_spring_profiles_receive_relevant_practices_and_flutter_is_isolated` |
| Autre profil (Flutter) | même test — Flutter isolé, aucune pratique Java ne fuite |
| Aucune organization practice | `test_project_can_use_only_local_knowledge_without_organization_catalog` (`organizationCatalogs: []`) |
| Plusieurs organization catalogs | **Non prouvé de bout en bout aujourd'hui.** Le mécanisme d'héritage (`extends`, détection de cycle, sélection de version) est unitairement vérifié sur des catalogues synthétiques (`test_missing_document_in_unreferenced_catalog_does_not_break_a_referenced_sibling`), mais le seul exemple réel à deux catalogues du repo (`gad-digital extends factory-default`) est bloqué par le sous-module externe injoignable — voir §Known limitations. |

## 6. Known limitations

- Résolution de plusieurs catalogues d'organisation avec du contenu réel :
  non démontrée en bout en bout dans cet environnement (dépendance externe
  injoignable, cf. ci-dessus).
- Level 3 (Engineering Outcome) est un contrat de schéma sans aucune
  mesure : `correctness`, `scopeRespect`, `testQuality`, `reviewFindings`,
  `rework`, `policyViolations` sont tous `not_evaluated`. AIEF ne sait pas
  aujourd'hui juger la qualité d'un changement produit par un agent.
- `PROVIDER_UNAVAILABLE` (échec de chargement du manifeste provider) est un
  code d'erreur défini dans `aief/provider_runtime.py` mais **jamais
  exercé par un test**, contrairement aux 4 autres codes du même module
  (`PROVIDER_NOT_CONFIGURED`, `CAPABILITY_UNSUPPORTED`, `MCP_NOT_CONFIGURED`,
  `AUTHENTICATION_REQUIRED`, tous couverts par `tests/test_tracking.py`).
- Les intégrations (GitHub/GitLab/Jira/Confluence) sont 100 % déclaratives
  côté AIEF : aucun code n'appelle réellement leurs API. C'est un choix
  d'architecture assumé (délégation au MCP), pas un défaut — mais cela
  signifie qu'AIEF ne garantit jamais qu'une opération déclarée fonctionne
  réellement côté provider.
- La promotion de connaissance (`aief/knowledge.py`) est entièrement
  implémentée et testée en isolation mais n'a aucun appelant dans le
  pipeline runtime réel — inatteignable en usage normal aujourd'hui.
- Les schémas `Artifact` et `Gate` (`artifact.schema.json`,
  `gate.schema.json`) restent orphelins : aucun document de ce `kind`
  n'existe nulle part dans le repo, le comportement réel des gates passe
  par un mécanisme ad hoc (`policyGates`, statuts d'Execution).

## 7. Operational risks

- **Dépendance externe non résiliente** : un sous-module git privé
  manquant a cassé, avant le correctif de cette série, la résolution de
  contexte pour *tout* projet, y compris ceux sans rapport avec ce
  catalogue. Le correctif isole ce risque au niveau projet, mais la
  dépendance externe elle-même (accès réseau/écritures à un repo privé)
  reste un point de fragilité pour tout clone frais ou CI sans les
  identifiants adéquats.
- **Profils sans commande de validation réelle** : `generic`, `node`,
  `java` (et par héritage `spring`, `react`, `flutter`) expédient des
  `commands: {}` vides — seul `maven` a de vraies commandes build/test. La
  validation de profil est un no-op silencieux pour la plupart des stacks
  tant qu'aucune commande n'est ajoutée.
- **Verrou de fichier best-effort** : les leases d'Execution et le journal
  d'opérations reposent sur `O_EXCL` mono-hôte ; aucun répartiteur, aucune
  garantie multi-hôte. Adapté à l'usage actuel (un agent, un dépôt local),
  pas à un futur scénario distribué sans réévaluation.
- **Export OpenTelemetry** : strictement optionnel et déjà testé comme non
  bloquant (`test_export_enabled_but_opentelemetry_unavailable_never_blocks_an_execution`)
  — risque résiduel faible, mais jamais exercé contre un vrai collecteur
  OTel dans cette session (seulement contre un module simulé).

## 8. Deferred features

- Export OpenTelemetry vers un collecteur réel (jamais testé en conditions réelles).
- Verrou de résolution de catalogue (`OrganizationLock`, content-addressed) — proposé en spec, non implémenté.
- Dépréciation de pratique (`deprecated`/`supersededBy`) — proposée en spec, non implémentée.
- Mise en application effective des politiques `change/context/external-action/traceability/recovery/memory/source-control-identity`.
- Level 3 (mesure réelle de l'Engineering Outcome) — contrat seul aujourd'hui.
- Gate/vérification du `requiresCapabilities` d'un Skill contre les intégrations réellement résolues avant exécution.

---

## READY FOR REAL PROJECT PILOT

- Le Runtime pour un **projet mono-organisation, mono-catalogue**
  (`factory-default` seul ou aucun catalogue), en **monorepo ou polyrepo**,
  sur les profils **Java/Spring/Maven/Flutter/generic** — 192 tests
  passants, preuves Level 1 et Level 2 exécutées et citées ci-dessus.
- L'exécution symétrique **Claude Code / Codex** sur la même Task, avec la
  même trajectoire Runtime observable et vérifiable après coup
  (`aief task log`).
- L'observabilité locale (JSONL structuré, redaction de secrets vérifiée,
  export externe strictement optionnel).
- Les gates humains, le tracking externe obligatoire, la sécurité de
  workspace (dépôt sale, poly-repo) — chacun bloque effectivement la
  mutation et se lève correctement à la résolution.

## NOT YET READY

- Une organisation avec **plusieurs catalogues d'organisation réels en
  production** (l'héritage inter-catalogues n'est pas prouvé de bout en
  bout dans cet environnement — dépendance externe à résoudre d'abord).
- Toute décision qui s'appuierait sur les politiques
  `change/context/external-action/traceability/recovery/memory` comme
  étant *appliquées* : elles sont aujourd'hui documentaires uniquement.
- Toute évaluation automatisée de la qualité du code produit
  (correctness, scope, tests, review, rework, violations) : Level 3 est un
  contrat vide, pas un outil de mesure.
- Un usage multi-hôte ou multi-agent concurrent au-delà d'un seul poste de
  travail : les leases sont mono-hôte, jamais testées en environnement
  distribué.
- La promotion de connaissance organisationnelle en usage réel : le
  mécanisme existe et est testé isolément, mais n'est relié à aucun
  déclencheur du pipeline aujourd'hui.
