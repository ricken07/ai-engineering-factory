# 33 — Evaluation Harness

AIEF ne compare pas des modèles avant de savoir qu'il respecte lui-même ses
propres contrats. Le harness (`aief/scenarios.py`) vérifie cela en trois
niveaux séparés. Ce n'est pas une plateforme de benchmark : douze scénarios
fixes, aucun dashboard, aucun état persistant au-delà de ce qu'un test
pytest écrit déjà dans `tmp_path`.

## Level 1 — Runtime Conformance (100 % déterministe)

Chaque scénario est un `Given/When/Then` exécuté directement contre le
Runtime (`RuntimeService`, `resolve_engineering_context`,
`evaluate_runtime_policy`, `resolve_task_provider`) — jamais via un agent
LLM. Douze scénarios couvrent : `simple-feature`, `natural-language-bug`,
`ambiguous-request`, `multi-repo-change`, `high-risk-change`,
`dirty-workspace`, `missing-provider`, `tracking-required`, `human-gate`,
`policy-conflict`, `organization-practice-override`,
`handoff-claude-to-codex`.

```python
from pathlib import Path
from aief.scenarios import run_scenario

result = run_scenario("high-risk-change", Path("."), Path("/tmp/scenario-run"))
```

## Level 2 — Adapter Conformance

Ne compare pas la qualité du code produit. Vérifie que le Runtime traite
`claude-code` et `codex` de façon strictement identique : même Task
normalisée, même Workflow compilé, même décision de policy, même contexte
d'ingénierie effectif, mêmes gates franchis. Techniquement, ce n'est **pas**
un second catalogue de scénarios : c'est le même scénario Level 1, rejoué
une fois par agent, dont les résultats sont diffés.

```python
from aief.scenarios import run_adapter_conformance

result = run_adapter_conformance("human-gate", Path("."), Path("/tmp/scenario-run"))
```

Les scénarios dont le chemin de code ne reçoit jamais d'identité d'agent
(`multi-repo-change`, `high-risk-change`, `policy-conflict`,
`organization-practice-override`, `handoff-claude-to-codex`) sont marqués
`agent_parametrized=False` : leur conformité inter-agent est déjà garantie
par construction (aucune branche liée à l'agent n'existe dans ce code), le
Level 2 le constate au lieu de rejouer un diff sans objet.

## Level 3 — Engineering Outcome (contrat uniquement)

`core/schemas/engineering-outcome.schema.json` fixe les six dimensions à
évaluer plus tard — correctness, scopeRespect, testQuality, reviewFindings,
rework, policyViolations — chacune `not_evaluated` tant qu'aucune exécution
agent réelle n'a produit de code à juger. `pending_engineering_outcome(...)`
produit un document valide contre ce schéma, sans aucune mesure :
l'évaluation réelle de la qualité du code reste hors périmètre d'AIEF
(elle appartient à l'agent et, plus tard, à un juge humain ou LLM séparé).

## Fixtures

Un seul projet minimal réutilisable (`templates/project`, via
`_seed_project`), avec des surcharges ciblées (autonomie, dépôts,
`taskTracking`) selon le scénario. Les scénarios multi-repo réutilisent
`examples/emmany`, déjà existant, plutôt que d'introduire une deuxième
fixture. Chaque scénario est reproductible : mêmes entrées, mêmes sorties,
sur toute machine (`tests/test_scenarios.py::test_scenarios_are_reproducible_across_independent_runs`).

## Reporting

`format_report(results)` produit un tableau texte simple — pas de dashboard :

```text
Scenario           Expected                                            Observed                              Status  Evidence
-----------------  --------------------------------------------------  ------------------------------------  ------  ------------------------------------------
ambiguous-request  Given an ambiguous request ...; then analyze-task    {'workflow': 'analyze-task', ...}      PASS    level1:ambiguous-request:agent=claude-code
dirty-workspace    Given a dirty local workspace ...; then blocked      {'status': 'blocked', ...}             PASS    level1:dirty-workspace:agent=claude-code
high-risk-change   Given HIGH risk ...; then autonomy <= L2             {'effectiveRisk': 'high', ...}         PASS    level1:high-risk-change:agent=claude-code
```

Une régression Runtime réelle (exception inattendue, pas un résultat testé)
apparaît en `FAIL` avec le type et le message de l'exception en `Observed` —
elle n'est jamais absorbée silencieusement.

## Tests

`tests/test_scenarios.py` fait tourner les douze scénarios en Level 1 et en
Level 2, vérifie que le rapport garde ses cinq colonnes, qu'une régression
simulée est bien rapportée en échec, que le contrat Level 3 valide son
schéma sans mesure, et que deux exécutions indépendantes du même scénario
produisent le même résultat.
