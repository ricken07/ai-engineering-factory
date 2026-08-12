# 31 — Ordonnancement des Tasks et readiness dérivée

## Objectif

Jusqu'en 1.14.0, la Factory n'avait aucune primitive d'ordre entre Tasks.
`aief intake` normalise une requête à la fois, `aief execution next` avance une
phase *à l'intérieur* d'une exécution déjà choisie, et la seule fonction
topologique du Runtime (`aief backlog apply`) ordonnait la *création* de tickets
externes, jamais leur exécution. La dépendance déclarée sur une
`ExternalTaskProposal` disparaissait du modèle d'état dès l'issue créée : elle
survivait dans le tracker, nulle part dans `.ai/runtime`.

Conséquence : l'ordre ne pouvait vivre que dans un fichier de pilotage lu par
l'agent, donc appliqué par discipline et non par contrainte — hors schéma, hors
`aief validate`, hors journal d'événements. C'est exactement la classe de
garantie que la Factory existe pour supprimer.

La version 1.15.0 comble ce trou sans introduire de scheduler : la dépendance
est **déclarée** sur la Task et gouvernée par schéma ; l'ordre et la
disponibilité sont **dérivés** de l'état, jamais déclarés.

## Ce que le projet déclare

`task.schema.json` accepte deux champs supplémentaires :

```yaml
kind: Task
metadata: {id: EGW-142}
parent: EGW-100          # hiérarchie — n'ordonne pas et ne bloque pas
dependsOn: [EGW-141]     # séquence — ordonne et bloque
objective: {summary: ...}
```

La distinction est volontaire. `parent` rattache une Task à son epic ; un epic
n'a pas à être terminé avant ses enfants. `dependsOn` exprime une précédence
réelle : tant que la dépendance n'est pas terminée, la Task n'est pas prenable.

Ces champs vivent dans `.ai/runtime/tasks/<id>/task.yaml`, donc dans le
périmètre scanné par `aief validate` : un `dependsOn` mal typé casse la
validation projet au lieu de passer silencieusement.

## Ce que le Runtime dérive

Le Runtime ne stocke aucun statut de Task. Il le recalcule :

```text
état de la Task   = statut de son Execution la plus récente
                    (aucune Execution → pending)
readiness         = fonction de (état, dépendances non satisfaites)
```

Les identifiants d'Execution portent un horodatage UTC, donc « la plus
récente » se résout par tri lexicographique, sans lire d'horloge.

| readiness | signification |
| --- | --- |
| `done` | une Execution `completed` existe |
| `blocked` | au moins une dépendance déclarée n'est pas terminée, ou est inconnue |
| `active` | une Execution possède déjà la Task, y compris encore `pending` |
| `ready` | rien n'empêche d'ouvrir une Execution |

Trois décisions explicites :

- Une Execution possède sa Task dès sa création, avant même sa première phase.
  Une Execution `pending` rend donc la Task `active` : sans cela, un agent
  pourrait en ouvrir une seconde sur le même travail.
- Une Execution `failed` ou `cancelled` laisse la Task `ready` : un échec est
  rejouable, pas terminal.
- Une référence `dependsOn` qui ne correspond à aucune Task enregistrée
  **bloque** et est reportée dans `unknownDependsOn`. Pas de fallback
  silencieux : une dépendance qu'on ne sait pas résoudre n'est pas une
  dépendance satisfaite.
- Un cycle de dépendances est une erreur, comme pour `backlog apply`. Le
  Runtime refuse de produire un ordre plutôt que d'en produire un faux.

Une Task qui affiche `readiness: blocked` avec `state: running` signale une
**violation d'ordre** : une exécution a démarré sur un travail dont les
prérequis ne sont pas satisfaits. Les deux champs sont exposés séparément pour
rendre ce cas visible.

## La commande

```bash
aief task list --project . --factory "$GAD_AI_FACTORY_HOME"
aief task list --ready --project . --factory "$GAD_AI_FACTORY_HOME"
```

La sortie est un artefact `TaskBacklog` validé contre
`core/schemas/task-backlog.schema.json` :

```yaml
kind: TaskBacklog
project: emmany-gateway
filter: ready
tasks:
  - task: EGW-141
    position: 1
    state: pending
    readiness: ready
    summary: Exposer le contrat Homework
    workflow: implement-task
    intent: implement
```

`--ready` ne retient que les Tasks prenables et renumérote les positions. Les
Tasks sont triées topologiquement par `dependsOn`, l'ordre entre Tasks
indépendantes étant stabilisé par identifiant.

La projection est **calculée à la lecture, jamais persistée**. Il n'existe donc
pas d'ordre à resynchroniser : l'état du Runtime est la seule source.

## Limite assumée

`aief task list` est une **lecture**, pas un gate. La Factory n'interdit pas
aujourd'hui d'ouvrir une Execution sur une Task `blocked` — elle le rend
visible et auditable. L'application dure de la précédence (blocage via
`blockingReason`, comme pour `external-tracking-required`) reste un choix
ouvert, à trancher quand l'usage aura montré si la visibilité suffit.

Conformément à `docs/19-idempotence-execution-leases.md`, aucun scheduler,
daemon, base de données ni verrou distribué n'est introduit.
