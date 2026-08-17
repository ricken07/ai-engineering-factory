# 32 — Observabilité légère du Runtime

AIEF n'est pas une plateforme d'observabilité : pas de dashboard propriétaire,
pas de serveur central, pas de message broker, pas de base dédiée. Ce que le
Runtime offre est un événement structuré, minimal, stocké localement, pour
chaque transition qu'il fait déjà transiter — jamais une seconde machine à
états parallèle à `Execution`.

## Event Envelope

Chaque événement suit un contrat unique, agent-neutre :

```yaml
event:
  id: event-abc123def456
  type: phase.completed
  timestamp: 2026-09-02T10:00:00+00:00
factory:
  version: 1.15.0
project:
  id: emmany
task:
  id: EGW-142
execution:      # absent pour request.created et intent.resolved,
  id: exec-142  # qui précèdent la création de l'Execution
payload: {}     # données spécifiques à l'événement, redigées (voir Sécurité)
```

Le contrat est décrit par `core/schemas/runtime-event.schema.json`. `event.type`
est une énumération fermée — un type non listé est rejeté par
`TaskEventLog.append`, pour empêcher la dérive de nommage libre.

## Stockage

Un fichier JSONL append-only par Task, agent-neutre, déjà en place avant cet
incrément :

```text
.ai/runtime/tasks/<task-id>/events.jsonl
```

C'est le seul backend requis. Rien d'autre n'est nécessaire pour utiliser
AIEF.

## Événements minimum

```text
request.created
intent.resolved
task.normalized
workflow.started

phase.started
phase.completed
phase.failed

policy.evaluated
policy.reclassified

gate.requested
gate.approved
gate.rejected

workspace.prepared
workspace.blocked

integration.resolved
integration.failed

execution.completed
execution.failed
execution.cancelled
```

Chacun réutilise une transition Runtime déjà existante — aucun n'a été ajouté
en créant un mécanisme parallèle :

| Événement | Transition Runtime réutilisée |
|---|---|
| `request.created`, `intent.resolved`, `task.normalized` | `RuntimeService.intake` (Request → IntentResolution → Task) |
| `workflow.started` | `Execution.create` |
| `phase.started` | `RuntimeService.prepare_phase` (matérialisation du contrat de Skill / contexte d'ingénierie) |
| `phase.completed` | `Execution.advance` sur succès |
| `phase.failed` | `Execution.fail_phase` |
| `policy.evaluated` / `policy.reclassified` | `RuntimeService.reassess_policy` ; `reclassified` seulement si le risque effectif ou l'autonomie autorisée changent réellement par rapport à la révision `PolicyDecision` précédente, sinon `evaluated` |
| `gate.requested` | une entrée `policyGates` ou une opération de tracking externe passe à `pending` |
| `gate.approved` / `gate.rejected` | `approve_execution`, `approve_policy_gate`, `TaskTrackingManager.approve` |
| `workspace.prepared` / `workspace.blocked` | `RuntimeService.workspace` et les blocages de sécurité workspace dans `prepare_phase` — remplace l'ancien nommage dynamique `workspace.<action>` |
| `integration.resolved` / `integration.failed` | `TaskTrackingManager.resolve_provider` (résolution MCP/provider) |
| `execution.completed` | `Execution.advance` quand `next_phase()` devient `None` |
| `execution.failed` | `Execution.fail_phase` (toute Execution actuelle échoue avec sa phase) |
| `execution.cancelled` | `Execution.cancel` — complète un statut `cancelled` déjà présent dans `common.schema.json#/$defs/executionStatus` et déjà vérifié partout (`readiness.py`, `service.py`) mais jusqu'ici jamais atteignable ; ce n'est pas une nouvelle machine à états, seulement la transition manquante vers un état déjà déclaré |

`run_profile_validation` n'émet pas d'événement `validation.*` dédié : ses
transitions passent par `complete_phase`/`fail_phase`, qui émettent déjà
`phase.completed`/`phase.failed`/`execution.*` avec `payload.phase ==
"validation"`. Un événement `validation.*` séparé aurait dupliqué exactement
le même fait sous un second nom — supprimé lors de l'audit de consolidation
(voir `docs/34-release-readiness.md`).

## Export

- **Par défaut** : événements structurés en local (`events.jsonl`). Toujours
  actif, jamais désactivable — c'est la seule source de vérité requise.
- **Optionnel** : export OpenTelemetry, activé uniquement par la variable
  d'environnement `AIEF_OBSERVABILITY_OTEL=1`. Sans elle, `opentelemetry`
  n'est même pas importé. Avec elle mais sans le paquet installé (ou toute
  autre erreur d'export), l'échec est absorbé silencieusement : une Execution
  normale n'est jamais bloquée par l'indisponibilité de l'exporteur. AIEF ne
  dépend d'aucun backend externe pour fonctionner.

## Sécurité

`TaskEventLog.append` redige le `payload` avant écriture :

- toute clé nommée `secret(s)`, `token(s)`, `password(s)`, `apikey`/`api_key`,
  `authorization`, `credential(s)`, `private(_)key` → valeur remplacée par
  `[REDACTED]` ;
- toute valeur correspondant à un motif de secret connu (clé AWS, jeton
  GitHub, jeton Slack, clé privée PEM, JWT) → `[REDACTED]`, où qu'elle
  apparaisse ;
- toute clé nommée `content`, `prompt(s)` ou `body` → `[OMITTED:opt-in
  required]` par défaut. Un appelant qui a une raison explicite d'inclure ce
  contenu doit passer `allow_content=True` — jamais le comportement par
  défaut.

Aucun prompt complet, aucun contenu source arbitraire et aucun contenu privé
du contexte projet (par exemple le texte d'une pratique d'ingénierie résolue)
n'est donc journalisé sans décision explicite au point d'appel.

## Ce que ce n'est pas

- Pas un remplacement des documents d'état (`Task`, `Execution`,
  `PolicyDecision`, ...), qui restent la source de vérité structurée et
  validée par schéma.
- Pas un système de conformité comportementale Claude/Codex à lui seul : les
  événements permettent de vérifier qu'une trajectoire a eu lieu, pas que
  deux agents produisent la même trajectoire — voir le futur harnais de
  scénarios pour cette preuve.
- Pas un journal d'audit réglementaire : il vit sous `.ai/runtime/`, gitignoré,
  et n'est pas reconstruit rétroactivement pour les Tasks antérieures à son
  introduction.
